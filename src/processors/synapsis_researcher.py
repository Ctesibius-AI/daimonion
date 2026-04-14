"""
Synapsis Step 3: Research -- Deep web research on flagged topics.

Reads from two sources:
1. research_queue.json (daytime flags from web_search tool)
2. Analyze step's research_flags (backward-looking pattern detection)

Merges, deduplicates, picks max 3 topics per night.
For each: Brave search -> refine -> Brave again -> compile report -> save to vault.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

import anthropic
import httpx

from src.config import MAX_RESEARCH_TOPICS_PER_NIGHT, SONNET_MODEL
from src.tools.research_queue import get_pending, mark_researched
from src.tools.usage_tracker import tracker
from src.tools.vault import save as save_to_vault

logger = logging.getLogger('daimonion.synapsis_researcher')

BRAVE_API_KEY = os.environ.get('BRAVE_SEARCH_API_KEY', '')
BRAVE_URL = 'https://api.search.brave.com/res/v1/web/search'

COMPILE_PROMPT = """You are compiling a research brief from web search results. Be factual and concise.

Structure:
1. **Executive Summary** (3 sentences max)
2. **Key Findings** (bullet points, each with source)
3. **Sources** (URLs)

Rules:
- Only state what the search results support. No inference beyond the data.
- Mark confidence: [confirmed] multiple sources confirm, [single-source] single source only.
- If results are thin or contradictory, say so explicitly.
- Under 500 words total.
"""

REFINE_PROMPT = """Based on the initial search results below, suggest a more specific follow-up search query that would fill the biggest gap in what we found. Return ONLY the search query string, nothing else."""


async def brave_search(query: str, num_results: int = 5) -> list[dict]:
    """Run a Brave web search."""
    if not BRAVE_API_KEY:
        logger.warning('Brave API key not configured')
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BRAVE_URL,
                params={'q': query, 'count': num_results},
                headers={'X-Subscription-Token': BRAVE_API_KEY, 'Accept': 'application/json'},
            )
            response.raise_for_status()
            data = response.json()

        # Log Brave search cost
        tracker.log_brave(query, result_count=len(data.get('web', {}).get('results', [])))

        results = []
        for item in data.get('web', {}).get('results', [])[:num_results]:
            results.append({
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'description': item.get('description', ''),
            })
        return results

    except Exception as e:
        logger.error('Brave search failed for "%s": %s', query, e)
        return []


def format_search_results(results: list[dict]) -> str:
    """Format search results as text for LLM."""
    lines = []
    for r in results:
        lines.append(f'**{r["title"]}**')
        lines.append(f'URL: {r["url"]}')
        if r['description']:
            lines.append(f'{r["description"]}')
        lines.append('')
    return '\n'.join(lines)


def slugify(text: str) -> str:
    """Convert topic to a filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:60].rstrip('-')


async def research_topic(
    client: anthropic.AsyncAnthropic,
    topic: str,
    reason: str,
    model: str = SONNET_MODEL,
) -> dict:
    """Research a single topic: search -> refine -> search -> compile -> save to vault.

    Returns dict with status, topic, vault_path, report summary.
    """
    logger.info('Researching: "%s" (reason: %s)', topic, reason)

    # Step 1: Initial broad search
    results_1 = await brave_search(topic, num_results=5)
    if not results_1:
        return {'status': 'no_results', 'topic': topic, 'reason': 'Initial search returned nothing'}

    formatted_1 = format_search_results(results_1)

    # Step 2: Refine search query
    try:
        refine_response = await client.messages.create(
            model=model,
            max_tokens=100,
            system=REFINE_PROMPT,
            messages=[{'role': 'user', 'content': f'Topic: {topic}\n\nInitial results:\n{formatted_1}'}],
        )
        tracker.log(refine_response, component='night_research_refine')
        refined_query = refine_response.content[0].text.strip()
        logger.info('Refined query: "%s"', refined_query)
    except Exception as e:
        logger.warning('Query refinement failed: %s -- using original', e)
        refined_query = topic

    # Step 3: Refined search
    results_2 = await brave_search(refined_query, num_results=5)
    formatted_2 = format_search_results(results_2) if results_2 else ''

    # Step 4: Compile report
    all_results = f'## Initial Search: "{topic}"\n\n{formatted_1}'
    if formatted_2:
        all_results += f'\n\n## Refined Search: "{refined_query}"\n\n{formatted_2}'

    try:
        compile_response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=COMPILE_PROMPT,
            messages=[{
                'role': 'user',
                'content': f'Topic: {topic}\nReason for research: {reason}\n\n{all_results}',
            }],
        )
        tracker.log(compile_response, component='night_research_compile')
        report = compile_response.content[0].text
    except Exception as e:
        logger.error('Report compilation failed: %s', e)
        report = f'# Research: {topic}\n\nCompilation failed: {e}\n\n## Raw Results\n\n{all_results}'

    # Step 5: Save to vault
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    slug = slugify(topic)
    vault_path = f'research/{slug}.md'

    full_report = (
        f'# Research: {topic}\n'
        f'**Date:** {date_str}\n'
        f'**Reason:** {reason}\n'
        f'**Searches:** "{topic}" + "{refined_query}"\n\n'
        f'---\n\n'
        f'{report}'
    )

    save_result = save_to_vault(vault_path, full_report, mode='update')
    logger.info('Research saved: %s (%s)', vault_path, save_result['status'])

    # Step 6: Mark as researched
    mark_researched(topic)

    return {
        'status': 'ok',
        'topic': topic,
        'vault_path': vault_path,
        'searches': [topic, refined_query],
        'result_count': len(results_1) + len(results_2),
    }


async def research(
    client: anthropic.AsyncAnthropic | None = None,
    analyze_flags: list[dict] | None = None,
    model: str = SONNET_MODEL,
    max_topics: int = MAX_RESEARCH_TOPICS_PER_NIGHT,
) -> list[dict]:
    """Run Step 3: Research.

    Args:
        client: Anthropic async client
        analyze_flags: research_flags from Analyze step output
        model: Model for compilation (default Sonnet)
        max_topics: Max topics per night (default 3)

    Returns:
        List of research result dicts.
    """
    if client is None:
        client = anthropic.AsyncAnthropic()

    # Merge sources: daytime queue + analyze flags
    topics = []

    # From daytime research queue
    queued = get_pending(max_topics=max_topics)
    for q in queued:
        topics.append({'topic': q['topic'], 'reason': q['reason'], 'source': 'daytime'})

    # From Analyze step
    if analyze_flags:
        for flag in analyze_flags:
            topic = flag.get('topic', '')
            reason = flag.get('reason', '')
            # Deduplicate against queue
            if topic and not any(t['topic'].lower() == topic.lower() for t in topics):
                topics.append({'topic': topic, 'reason': reason, 'source': 'night_analyzer'})

    # Cap at max
    topics = topics[:max_topics]

    if not topics:
        logger.info('No research topics for tonight')
        return []

    logger.info('Researching %d topics tonight', len(topics))

    # Research each topic
    results = []
    for t in topics:
        try:
            result = await research_topic(client, t['topic'], t['reason'], model)
            results.append(result)
        except Exception as e:
            logger.error('Research failed for "%s": %s', t['topic'], e)
            results.append({'status': 'error', 'topic': t['topic'], 'error': str(e)})

    return results

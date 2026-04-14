"""
Synapsis Step 4: Compile -- Build morning briefing and update vault wiki pages.

Step 4a: Morning briefing -> vault/daily-briefings/ + hot_cache.md
Step 4b: Wiki compilation -> update vault pages from knowledge entries (incremental)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import anthropic

from src.config import (
    DEFAULT_CITY,
    HAIKU_MODEL,
    HOT_CACHE_MD,
    KNOWLEDGE_DIR,
    USAGE_DIR,
    VAULT_DIR,
)
from src.tools.usage_tracker import tracker
from src.tools.vault import read as read_from_vault
from src.tools.vault import save as save_to_vault

logger = logging.getLogger('daimonion.synapsis_compiler')

BRIEFING_PROMPT = """You are compiling the morning briefing. This is what the user sees first thing tomorrow morning. Be concise, direct, useful.

Structure:
1. **Weather** (if provided)
2. **Overnight Research** (if any research reports were produced -- include executive summary + link)
3. **Pending Decisions** (from Analyze -- what needs deciding, with context)
4. **Active Projects** (from Analyze -- momentum per project)
5. **Patterns** (from Analyze -- what the user should be aware of)
6. **Follow-ups** (action items due)

Rules:
- Under 500 words. This goes into the system prompt.
- No filler. Every line must be actionable or awareness-building.
- Use [[wiki-links]] when referencing vault pages.
- If a section has nothing: skip it entirely. Don't write "No research tonight."
- Write in second person: "You've been focused on..." not "The user has been..."

Output: Markdown. No JSON wrapper.
"""


async def compile_briefing(
    client: anthropic.AsyncAnthropic | None = None,
    analysis: dict | None = None,
    research_results: list[dict] | None = None,
    extract_stats: dict | None = None,
    target_date: str | None = None,
    model: str = HAIKU_MODEL,
) -> dict:
    """Step 4a: Compile morning briefing.

    Args:
        client: Anthropic async client
        analysis: Output from Step 2 (Analyze)
        research_results: Output from Step 3 (Research)
        extract_stats: Stats from Step 1 (Extract)
        target_date: Date for the briefing (default: today)
        model: Model for compilation (default: Haiku)

    Returns:
        dict with status, briefing text, paths saved.
    """
    if client is None:
        client = anthropic.AsyncAnthropic()

    date = target_date or datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Build input from all previous steps
    sections = []

    # Weather
    try:
        from src.tools.weather import get_weather
        weather = get_weather(DEFAULT_CITY)
        if weather:
            sections.append('## Weather -- ' + DEFAULT_CITY + '\n' + weather)
    except Exception as e:
        logger.warning('Weather fetch failed: %s', e)

    # Analysis results
    if analysis:
        if analysis.get('pending_decisions'):
            decisions = '\n'.join(
                f'- **{d.get("decision", "?")}** -- {d.get("status", "open")}. {d.get("context", "")}'
                for d in analysis['pending_decisions']
                if isinstance(d, dict)
            )
            if decisions:
                sections.append(f'## Pending Decisions\n{decisions}')

        if analysis.get('project_momentum'):
            projects = '\n'.join(
                f'- **{p.get("project", "?")}**: {p.get("engagement", "?")} engagement, {p.get("trend", "?")}'
                for p in analysis['project_momentum']
                if isinstance(p, dict)
            )
            if projects:
                sections.append(f'## Active Projects\n{projects}')

        if analysis.get('patterns'):
            patterns = '\n'.join(f'- {p}' for p in analysis['patterns'])
            sections.append(f'## Patterns\n{patterns}')

        if analysis.get('recurring_topics'):
            topics = '\n'.join(
                f'- {t.get("topic", "?")} -- mentioned {t.get("days_mentioned", "?")} days, {t.get("trend", "?")}'
                for t in analysis['recurring_topics']
                if isinstance(t, dict)
            )
            if topics:
                sections.append(f'## Recurring Topics\n{topics}')

    # Research results
    if research_results:
        researched = [r for r in research_results if r.get('status') == 'ok']
        if researched:
            research_lines = []
            for r in researched:
                slug = r.get('vault_path', '').replace('.md', '')
                research_lines.append(f'- **{r.get("topic", "?")}** -- [[{slug}]]')
            sections.append(f'## Overnight Research\n' + '\n'.join(research_lines))

    # Extract stats
    if extract_stats:
        mem_count = extract_stats.get('memories_written', 0)
        kb_count = extract_stats.get('knowledge_promoted', 0)
        if mem_count or kb_count:
            sections.append(f'## Yesterday\'s Activity\n- {mem_count} memories extracted, {kb_count} knowledge entries promoted')

    # Usage summary from yesterday
    try:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_path = os.path.join(USAGE_DIR, f'{yesterday}.json')
        if os.path.exists(yesterday_path):
            with open(yesterday_path) as f:
                usage = json.load(f)
            mtd = tracker.get_month_to_date()
            usage_lines = [
                f'- Yesterday: {usage["total_calls"]} API calls, ${usage["total_cost_usd"]:.2f}',
                f'- Month-to-date: ${mtd["total_cost_usd"]:.2f} | Projected: ${mtd["projected_monthly_usd"]:.2f}/month',
            ]
            sections.append(f'## Usage\n' + '\n'.join(usage_lines))
    except Exception:
        pass

    # Health summary
    try:
        from src.processors.health_monitor import get_health_summary
        health_text = get_health_summary(date)
        if health_text:
            sections.append(health_text)
    except Exception:
        pass

    # QA findings
    try:
        from src.processors.qa_auditor import get_briefing_line
        qa_line = get_briefing_line()
        if qa_line:
            sections.append(f'## {qa_line}')
    except Exception:
        pass

    if not sections:
        briefing = f'# Morning Briefing -- {date}\n\nQuiet night. No significant updates.'
    else:
        # If we have enough content, let LLM synthesize
        raw_input = f'Date: {date}\n\n' + '\n\n'.join(sections)

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=2048,
                system=BRIEFING_PROMPT,
                messages=[{'role': 'user', 'content': raw_input}],
            )
            tracker.log(response, component='night_compile_briefing')
            briefing = f'# Morning Briefing -- {date}\n\n' + response.content[0].text
            logger.info('Briefing compiled: %d input tokens, %d output tokens',
                       response.usage.input_tokens, response.usage.output_tokens)
        except Exception as e:
            logger.error('Briefing compilation failed: %s -- using raw sections', e)
            briefing = f'# Morning Briefing -- {date}\n\n' + '\n\n'.join(sections)

    # Save to vault
    briefing_path = f'daily-briefings/{date}.md'
    save_to_vault(briefing_path, briefing, mode='update')
    logger.info('Briefing saved: vault/%s', briefing_path)

    # Update hot_cache.md with the briefing content
    try:
        _update_hot_cache(briefing, date)
        logger.info('Hot cache updated')
    except Exception as e:
        logger.warning('Hot cache update failed: %s', e)

    return {
        'status': 'ok',
        'date': date,
        'briefing_path': briefing_path,
        'briefing_length': len(briefing),
    }


def _update_hot_cache(briefing: str, date: str):
    """Write AAAK-compressed hot cache with ref pointers.

    Format: 9-day sliding window. Each day is a few AAAK lines.
    Today's briefing is included in full (prose). Days 2-9 are AAAK compressed.
    Each AAAK line carries ref: for drill-down into the triangle.
    """
    # Read existing hot cache to preserve older days
    existing_days = {}
    if os.path.exists(HOT_CACHE_MD):
        try:
            with open(HOT_CACHE_MD) as f:
                content = f.read()
            # Parse existing AAAK days (lines starting with date pattern)
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped and stripped[:4].isdigit() and '|' in stripped:
                    day_key = stripped.split('|')[0].strip()
                    existing_days.setdefault(day_key, []).append(stripped)
        except Exception:
            pass

    # Compress today into AAAK lines from briefing
    today_aaak = _briefing_to_aaak(briefing, date)

    # Build 9-day window
    from datetime import timedelta
    today = datetime.strptime(date, '%Y-%m-%d')
    cutoff = (today - timedelta(days=9)).strftime('%Y-%m-%d')

    # Remove days older than 9
    existing_days = {k: v for k, v in existing_days.items() if k >= cutoff}

    # Add today
    existing_days[date] = today_aaak

    # Build hot cache
    lines = [f'# Hot Cache — {date} (9-day AAAK index)\n']

    # Today gets the full briefing
    lines.append(f'## Today ({date})')
    lines.append(briefing)
    lines.append('')

    # Previous days get AAAK only
    for day in sorted(existing_days.keys(), reverse=True):
        if day == date:
            continue
        lines.append(f'## {day}')
        lines.extend(existing_days[day])
        lines.append('')

    content = '\n'.join(lines)
    tmp = HOT_CACHE_MD + '.tmp'
    os.makedirs(os.path.dirname(HOT_CACHE_MD), exist_ok=True)
    with open(tmp, 'w') as f:
        f.write(content)
    os.replace(tmp, HOT_CACHE_MD)


def _briefing_to_aaak(briefing: str, date: str) -> list[str]:
    """Compress a prose briefing into AAAK lines with ref pointers."""
    aaak_lines = []

    for line in briefing.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Extract key terms and compress
        if 'decision' in line.lower() or 'decided' in line.lower():
            importance = '★★★★'
        elif 'fixed' in line.lower() or 'built' in line.lower() or 'created' in line.lower():
            importance = '★★★★'
        elif 'pattern' in line.lower() or 'drift' in line.lower():
            importance = '★★★'
        elif 'weather' in line.lower():
            continue  # Skip weather in AAAK
        else:
            importance = '★★'

        # Compress: remove markdown, shorten
        compressed = line.lstrip('- *').rstrip('*').strip()
        if len(compressed) > 120:
            compressed = compressed[:117] + '...'
        if compressed:
            aaak_lines.append(f'{date}|{compressed}|{importance}')

    return aaak_lines


async def compile_wiki_pages(
    client: anthropic.AsyncAnthropic | None = None,
    model: str = HAIKU_MODEL,
) -> dict:
    """Step 4b: Wiki compilation -- update vault pages from accumulated knowledge.

    Reads knowledge entries, groups by entity, compiles structured pages for entities
    with 3+ facts. Incremental -- only updates pages where content has changed.

    Returns dict with status and pages updated.
    """
    if client is None:
        client = anthropic.AsyncAnthropic()

    if not os.path.exists(KNOWLEDGE_DIR):
        return {'status': 'ok', 'pages_updated': 0, 'reason': 'No knowledge entries'}

    # Load all knowledge entries
    entries = []
    for fname in os.listdir(KNOWLEDGE_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(KNOWLEDGE_DIR, fname)) as f:
                entries.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue

    if not entries:
        return {'status': 'ok', 'pages_updated': 0}

    # Group by entity — extract from 'entities' field or infer from category
    entity_facts: dict[str, list[dict]] = {}
    for entry in entries:
        entities_list = entry.get('entities', [])
        if not entities_list:
            # Infer entity from category or fact content
            cat = entry.get('category', '')
            fact = entry.get('fact', entry.get('content', ''))
            # Use first capitalized multi-word term or category as entity
            if cat:
                entities_list = [cat]
        for entity in entities_list:
            entity_facts.setdefault(entity, []).append(entry)

    # Compile pages for entities with 3+ facts
    pages_updated = 0
    for entity, facts in entity_facts.items():
        if len(facts) < 3:
            continue

        # Build the page content
        slug = entity.lower().replace(' ', '-')
        vault_path = f'projects/{slug}.md'

        # Check if page exists and has the same fact count
        existing = read_from_vault(vault_path)
        existing_content = existing.get('content', '') if existing.get('status') == 'ok' else ''

        # Simple change detection: count facts mentioned
        fact_texts = [f.get('fact', f.get('content', '')) for f in facts]
        fact_summary = '\n'.join(f'- {t}' for t in fact_texts)

        # Skip if no new facts (rough check -- count lines with content)
        existing_fact_lines = len([l for l in existing_content.split('\n') if l.startswith('- ') and len(l) > 10])
        if existing_fact_lines >= len(facts):
            continue

        # Compile page
        dates = sorted(set(f.get('source_date', '') for f in facts if f.get('source_date')))
        domains = sorted(set(f.get('domain', f.get('category', '')) for f in facts if f.get('domain') or f.get('category')))

        page_content = (
            f'# {entity}\n\n'
            f'*Auto-compiled from {len(facts)} knowledge entries*\n'
            f'*Dates: {dates[0] if dates else "?"} to {dates[-1] if dates else "?"}*\n'
            f'*Domains: {", ".join(domains)}*\n\n'
            f'## Key Facts\n\n{fact_summary}\n'
        )

        save_to_vault(vault_path, page_content, mode='update')
        pages_updated += 1
        logger.info('Wiki page updated: %s (%d facts)', vault_path, len(facts))

    return {
        'status': 'ok',
        'pages_updated': pages_updated,
        'entities_checked': len(entity_facts),
    }


async def compile(
    client: anthropic.AsyncAnthropic | None = None,
    analysis: dict | None = None,
    research_results: list[dict] | None = None,
    extract_stats: dict | None = None,
    target_date: str | None = None,
) -> dict:
    """Run Step 4: Compile (briefing + wiki).

    Args:
        client: Anthropic async client
        analysis: Output from Step 2
        research_results: Output from Step 3
        extract_stats: Stats from Step 1
        target_date: Date for briefing

    Returns:
        Combined results from briefing and wiki compilation.
    """
    if client is None:
        client = anthropic.AsyncAnthropic()

    # 4a: Morning briefing
    briefing_result = await compile_briefing(
        client, analysis, research_results, extract_stats, target_date,
    )

    # 4b: Wiki compilation
    wiki_result = await compile_wiki_pages(client)

    return {
        'briefing': briefing_result,
        'wiki': wiki_result,
    }

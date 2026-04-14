"""
Night Processor Step 2: Analyze — Incremental analysis.

Analyzes ONLY today's new memories, but reads the last 7 nights' analysis
outputs for context. Each night builds on the last — no re-processing.

Cheaper, smarter, faster than re-analyzing 7 days of raw memories every night.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import anthropic

from src.config import (
    BASELINE_PATTERNS_PATH,
    MEMORIES_DIR,
    NIGHT_RUNS_DIR,
    SONNET_MODEL,
)
from src.tools.usage_tracker import tracker

logger = logging.getLogger('daimonion.night_analyzer')

ANALYZE_PROMPT = """You are the Night Analyzer. You receive:
1. TODAY'S new memories (just extracted tonight)
2. The PREVIOUS 7 NIGHTS' analysis summaries (what was already found)
3. Baseline patterns (long-term behavioral reference)

Your job: UPDATE the running analysis with today's new data. Don't re-discover what previous nights already found — build on it.

## What to produce:

### 1. RECURRING TOPICS
Topics appearing on 2+ different days. Check previous analyses — if a topic was already flagged, update its count and trend. Add new topics from today.
- topic, days_mentioned, trend (increasing/stable/decreasing)

### 2. PENDING DECISIONS
Decisions raised but not resolved. Check previous analyses:
- If a previous decision was resolved today → mark it (don't include)
- If a previous decision is still open → update status
- If a new decision appeared today → add it
- decision, first_raised, status (open/leaning/stale/resolved), context

### 3. RESEARCH FLAGS
Topics needing actual data. Only flag NEW topics from today that previous nights haven't already researched. Check previous analyses to avoid re-flagging.
- topic, reason

### 4. PROJECT MOMENTUM
Update project engagement based on today's activity:
- If a project was discussed today → engagement up
- If a project wasn't discussed → check how many days since last mention
- project, engagement (high/medium/low), trend (accelerating/steady/stalling/stalled)

### 5. PATTERNS
New observations from TODAY only. What shifted? What's different from previous nights? Max 3 patterns — only genuinely new insights.

### 6. BASELINE DRIFT
Compare today's behavior against baseline patterns. Only report if today showed evidence of drift or evolution.
- pattern, status (reinforced/drifting/evolved), note

## Output: STRICT JSON

```json
{
  "recurring_topics": [
    {"topic": "...", "days_mentioned": 0, "trend": "increasing|stable|decreasing"}
  ],
  "pending_decisions": [
    {"decision": "...", "first_raised": "YYYY-MM-DD", "status": "open|leaning|stale|resolved", "context": "..."}
  ],
  "research_flags": [
    {"topic": "...", "reason": "..."}
  ],
  "project_momentum": [
    {"project": "...", "engagement": "high|medium|low", "trend": "accelerating|steady|stalling|stalled"}
  ],
  "patterns": ["...", "..."],
  "baseline_drift": [
    {"pattern": "...", "status": "reinforced|drifting|evolved", "note": "..."}
  ]
}
```

## Rules
- INCREMENTAL: Don't repeat what previous nights already found. Update, evolve, or resolve.
- If today had no conversations, output empty lists — don't fabricate.
- Pending decisions not mentioned for 3+ days → mark as stale.
- Projects not mentioned for 3+ days → trend = stalled.
- Be concise. This feeds the morning briefing.
"""


def load_today_memories(target_date: str) -> list[dict]:
    """Load only today's memories."""
    if not os.path.exists(MEMORIES_DIR):
        return []

    memories = []
    for fname in sorted(os.listdir(MEMORIES_DIR)):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(MEMORIES_DIR, fname)) as f:
                mem = json.load(f)
            if mem.get('source_date') == target_date and not mem.get('archived'):
                memories.append(mem)
        except (json.JSONDecodeError, KeyError):
            continue

    return memories


def load_previous_analyses(target_date: str, days: int = 7) -> list[dict]:
    """Load the last N nights' step2_analyze.json outputs."""
    analyses = []
    end = datetime.strptime(target_date, '%Y-%m-%d')

    for d in range(1, days + 1):
        date_str = (end - timedelta(days=d)).strftime('%Y-%m-%d')
        path = os.path.join(NIGHT_RUNS_DIR, date_str, 'step2_analyze.json')
        if os.path.exists(path):
            try:
                with open(path) as f:
                    analysis = json.load(f)
                analysis['_date'] = date_str
                analyses.append(analysis)
            except (json.JSONDecodeError, IOError):
                continue

    return analyses


def load_baseline_patterns() -> str:
    """Load baseline_patterns.md for drift tracking."""
    if not os.path.exists(BASELINE_PATTERNS_PATH):
        return ''
    try:
        with open(BASELINE_PATTERNS_PATH) as f:
            return f.read()
    except Exception:
        return ''


def format_today_memories(memories: list[dict]) -> str:
    """Format today's memories for the LLM."""
    if not memories:
        return 'No new memories extracted today.'

    lines = []
    for mem in memories:
        collection = mem.get('collection', '')
        content = mem.get('content', '')
        entities = ', '.join(mem.get('entities', []))
        significance = mem.get('significance', '')
        tag = f' [{collection}]' if collection else ''
        ent = f' (entities: {entities})' if entities else ''
        sig = f' [{significance}]' if significance else ''
        lines.append(f'- {content}{tag}{ent}{sig}')

    return '\n'.join(lines)


def format_previous_analyses(analyses: list[dict]) -> str:
    """Format previous nights' analyses as context."""
    if not analyses:
        return 'No previous analyses available (first night).'

    lines = []
    for a in sorted(analyses, key=lambda x: x.get('_date', '')):
        date = a.get('_date', '?')
        lines.append(f'\n### Night of {date}')

        topics = a.get('recurring_topics', [])
        if topics:
            lines.append('Recurring: ' + ', '.join(
                f'{t.get("topic", "?")} ({t.get("days_mentioned", "?")}d, {t.get("trend", "?")})'
                for t in topics if isinstance(t, dict)
            ))

        decisions = a.get('pending_decisions', [])
        if decisions:
            lines.append('Decisions: ' + ', '.join(
                f'{d.get("decision", "?")} [{d.get("status", "?")}]'
                for d in decisions if isinstance(d, dict)
            ))

        projects = a.get('project_momentum', [])
        if projects:
            lines.append('Projects: ' + ', '.join(
                f'{p.get("project", "?")} ({p.get("engagement", "?")}, {p.get("trend", "?")})'
                for p in projects if isinstance(p, dict)
            ))

        patterns = a.get('patterns', [])
        if patterns:
            lines.append('Patterns: ' + '; '.join(str(p) for p in patterns[:3]))

        flags = a.get('research_flags', [])
        if flags:
            lines.append('Research flagged: ' + ', '.join(
                f.get('topic', '?') if isinstance(f, dict) else str(f) for f in flags
            ))

    return '\n'.join(lines)


async def analyze(
    client: anthropic.AsyncAnthropic | None = None,
    today_memories: list[dict] | None = None,
    target_date: str | None = None,
    model: str = SONNET_MODEL,
) -> dict:
    """Run Step 2: Analyze (incremental).

    Analyzes only today's memories, using previous 7 nights' outputs as context.

    Args:
        client: Anthropic async client
        today_memories: Today's extracted memories (from Step 1). If None, loads from disk.
        target_date: Date to analyze (default: today)
        model: Model to use (default: Sonnet)

    Returns:
        Analysis dict with recurring_topics, pending_decisions, research_flags,
        project_momentum, patterns, baseline_drift.
    """
    if client is None:
        client = anthropic.AsyncAnthropic()

    date = target_date or datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Load today's memories (from Step 1 output or disk)
    if today_memories is None:
        today_memories = load_today_memories(date)
    logger.info('Today: %d memories to analyze', len(today_memories))

    # Load previous 7 nights' analysis outputs
    prev_analyses = load_previous_analyses(date, days=7)
    logger.info('Previous analyses: %d nights of context', len(prev_analyses))

    if not today_memories and not prev_analyses:
        logger.warning('No memories and no previous analyses — nothing to analyze')
        return _empty_analysis()

    # Format inputs
    today_text = format_today_memories(today_memories)
    prev_text = format_previous_analyses(prev_analyses)

    # Load baseline patterns (truncated for context window)
    baseline = load_baseline_patterns()
    baseline_section = ''
    if baseline:
        baseline_section = (
            '\n\n---\n\n## BASELINE PATTERNS (for drift tracking)\n\n'
            + baseline[:3000]
        )

    # Build input
    input_text = (
        f'## Date: {date}\n\n'
        f'## TODAY\'S NEW MEMORIES ({len(today_memories)} extracted)\n\n'
        f'{today_text}\n\n'
        f'---\n\n'
        f'## PREVIOUS 7 NIGHTS\' ANALYSES ({len(prev_analyses)} available)\n\n'
        f'{prev_text}'
        f'{baseline_section}'
    )

    logger.info('Analyze input: %d chars (~%d tokens)', len(input_text), len(input_text) // 4)

    # Call Sonnet
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=ANALYZE_PROMPT,
        messages=[{'role': 'user', 'content': input_text}],
    )

    tracker.log(response, component='night_analyze')

    raw = response.content[0].text
    logger.info('Analyze: %d input tokens, %d output tokens',
                response.usage.input_tokens, response.usage.output_tokens)

    # Parse JSON
    if raw.strip().startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        raw = re.sub(r'\s*```$', '', raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error('Failed to parse analysis JSON')
        result = _empty_analysis()
        result['_raw'] = raw

    logger.info(
        'Analysis: %d recurring, %d decisions, %d flags, %d projects, %d patterns',
        len(result.get('recurring_topics', [])),
        len(result.get('pending_decisions', [])),
        len(result.get('research_flags', [])),
        len(result.get('project_momentum', [])),
        len(result.get('patterns', [])),
    )

    return result


def _empty_analysis() -> dict:
    return {
        'recurring_topics': [],
        'pending_decisions': [],
        'research_flags': [],
        'project_momentum': [],
        'patterns': [],
        'baseline_drift': [],
    }

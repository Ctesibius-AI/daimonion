"""
MEMORY.md Compiler — Builds the AAAK multi-vertex index.

Reads the last 9 days of memories and knowledge, formats each as a
hyperedge line with refs into MemPalace, KG, Graphiti, and Wiki.

Output: MEMORY.md at the native Claude Code path, ≤200 lines, 9-day rolling.

Sparse ref convention:
  TBD — Synapsis hasn't processed this yet (pending)
  N/A — Synapsis evaluated, no ref warranted (excluded)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from src.config import (
    KNOWLEDGE_DIR,
    MEMORIES_DIR,
    MEMORY_MD_PATH,
    VAULT_DIR,
)

logger = logging.getLogger('daimonion.memory_index_compiler')

# Significance → star rating
STAR_MAP = {
    'critical': '★★★★★',
    'high': '★★★★',
    'medium': '★★★',
    'low': '★★',
    'trivial': '★',
}


def compile_memory_index(date: str | None = None, window_days: int = 9) -> dict:
    """Build MEMORY.md from the last N days of memories and knowledge.

    Args:
        date: Reference date (YYYY-MM-DD). Defaults to today.
        window_days: How many days to include. Default 9.

    Returns:
        Summary dict with line counts and path.
    """
    date = date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    ref_date = datetime.strptime(date, '%Y-%m-%d')
    cutoff = (ref_date - timedelta(days=window_days)).strftime('%Y-%m-%d')

    # Collect entries from both systems
    entries = []
    entries.extend(_load_memories(cutoff))
    entries.extend(_load_knowledge(cutoff))

    # Sort by date descending, then by significance
    sig_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'trivial': 4}
    entries.sort(key=lambda e: (-_date_rank(e['date'], date), sig_order.get(e['significance'], 3)))

    # Cap at 190 lines (leave room for header)
    entries = entries[:190]

    # Build the index
    lines = _build_header(date, window_days, len(entries))
    for entry in entries:
        lines.append(_format_aaak_line(entry))

    # Write to native path
    os.makedirs(os.path.dirname(MEMORY_MD_PATH), exist_ok=True)
    content = '\n'.join(lines) + '\n'
    with open(MEMORY_MD_PATH, 'w') as f:
        f.write(content)

    logger.info('MEMORY.md written: %d entries, %d lines → %s', len(entries), len(lines), MEMORY_MD_PATH)

    return {
        'path': MEMORY_MD_PATH,
        'entries': len(entries),
        'lines': len(lines),
        'window': f'{cutoff} → {date}',
    }


def _build_header(date: str, window_days: int, entry_count: int) -> list[str]:
    """Build the MEMORY.md header."""
    return [
        f'# MEMORY.md — {date}',
        f'# {window_days}-day rolling index | {entry_count} entries',
        f'# Format: date|summary|mp:ref|kg:ref|gr:ref|wiki:ref|significance',
        f'# Refs: TBD=pending Synapsis | N/A=evaluated, excluded',
        '',
    ]


def _format_aaak_line(entry: dict) -> str:
    """Format a single entry as an AAAK hyperedge line."""
    date = entry['date']
    summary = entry['summary']
    mp_ref = entry.get('mp_ref', 'TBD')
    kg_ref = entry.get('kg_ref', 'TBD')
    gr_ref = entry.get('gr_ref', 'TBD')
    wiki_ref = entry.get('wiki_ref', 'TBD')
    stars = STAR_MAP.get(entry.get('significance', 'medium'), '★★★')

    return f'{date}|{summary}|mp:{mp_ref}|kg:{kg_ref}|gr:{gr_ref}|wiki:{wiki_ref}|{stars}'


def _load_memories(cutoff: str) -> list[dict]:
    """Load memories from JSON files, filtered by cutoff date."""
    entries = []
    if not os.path.isdir(MEMORIES_DIR):
        return entries

    for fname in os.listdir(MEMORIES_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(MEMORIES_DIR, fname)) as f:
                mem = json.load(f)

            source_date = mem.get('source_date', '')
            if source_date < cutoff:
                continue
            if mem.get('archived', False):
                continue
            if mem.get('decay_score', 1.0) < 0.1:
                continue

            # Build summary from content (truncate to ~80 chars, dot-separated)
            content = mem.get('content', '')
            summary = _summarize(content)

            # MemPalace ref is the memory ID (it's also in ChromaDB)
            mp_ref = mem.get('memory_id', 'TBD')

            # Knowledge-promoted memories may have a kg ref
            kg_ref = 'N/A'  # memories are episodic, not KG triples

            # Graphiti ref — TBD until Synapsis QA promotes it
            gr_ref = 'TBD'

            # Wiki ref — check if a vault page might reference this
            wiki_ref = 'TBD'

            entries.append({
                'date': source_date,
                'summary': summary,
                'mp_ref': mp_ref,
                'kg_ref': kg_ref,
                'gr_ref': gr_ref,
                'wiki_ref': wiki_ref,
                'significance': mem.get('significance', 'medium'),
                'type': 'memory',
            })
        except (json.JSONDecodeError, IOError):
            continue

    return entries


def _load_knowledge(cutoff: str) -> list[dict]:
    """Load knowledge entries from JSON files, filtered by cutoff date."""
    entries = []
    if not os.path.isdir(KNOWLEDGE_DIR):
        return entries

    for fname in os.listdir(KNOWLEDGE_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(KNOWLEDGE_DIR, fname)) as f:
                kb = json.load(f)

            source_date = kb.get('source_date', '')
            if source_date < cutoff:
                continue

            fact = kb.get('fact', '')
            summary = _summarize(fact)
            category = kb.get('category', 'general')

            # Knowledge entries have KG refs (they are facts)
            kg_ref = f'{category}→{_slug(summary[:40])}'

            # MemPalace ref — may exist if bridged
            mp_ref = kb.get('knowledge_id', 'TBD')

            # Graphiti — TBD until promoted
            gr_ref = 'TBD'

            # Wiki — check vault decisions/projects
            wiki_ref = _find_wiki_ref(category, summary)

            entries.append({
                'date': source_date,
                'summary': summary,
                'mp_ref': mp_ref,
                'kg_ref': kg_ref,
                'gr_ref': gr_ref,
                'wiki_ref': wiki_ref,
                'significance': _kb_significance(kb),
                'type': 'knowledge',
            })
        except (json.JSONDecodeError, IOError):
            continue

    return entries


def _summarize(text: str, max_len: int = 80) -> str:
    """Compress text into a dot-separated summary for the AAAK line."""
    # Strip whitespace, take first sentence or max_len chars
    text = text.strip().replace('\n', ' ').replace('|', '/')
    if len(text) <= max_len:
        return text.replace(' ', '.')
    # Truncate at word boundary
    truncated = text[:max_len].rsplit(' ', 1)[0]
    return truncated.replace(' ', '.') + '...'


def _slug(text: str) -> str:
    """Convert text to a simple slug for refs."""
    return text.lower().replace(' ', '_').replace('.', '_')[:30]


def _date_rank(entry_date: str, ref_date: str) -> int:
    """Rank by recency (higher = more recent). Used for sorting."""
    try:
        ed = datetime.strptime(entry_date, '%Y-%m-%d')
        rd = datetime.strptime(ref_date, '%Y-%m-%d')
        return (ed - rd).days  # negative = older, 0 = today
    except ValueError:
        return -999


def _kb_significance(kb: dict) -> str:
    """Derive significance from knowledge entry confidence."""
    conf = kb.get('confidence', 0.5)
    if conf >= 0.9:
        return 'high'
    if conf >= 0.7:
        return 'medium'
    return 'low'


def _find_wiki_ref(category: str, summary: str) -> str:
    """Check if a vault page exists for this category."""
    # Check common vault subdirs
    for subdir in ('decisions', 'projects', 'research'):
        dir_path = os.path.join(VAULT_DIR, subdir)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if fname.endswith('.md'):
                # Simple heuristic: if category matches subdir name
                if subdir == 'decisions' and category in ('decision', 'architecture', 'technical'):
                    return f'{subdir}/{fname[:-3]}'
                if subdir == 'projects' and category in ('project', 'business'):
                    return f'{subdir}/{fname[:-3]}'
    return 'TBD'

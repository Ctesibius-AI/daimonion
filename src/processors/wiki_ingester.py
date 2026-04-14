"""
Wiki Ingester — Routes documents from vault/raw/ into the wiki structure.

Reads markdown files from vault/raw/, classifies them by filename pattern,
moves them to the appropriate wiki subdirectory, and updates the vault index.

No LLM needed. Pure file routing based on naming conventions.

Document types:
  synapsis-report-*.md  → synapsis-runs/     (run reports)
  research-*.md         → research/           (research compilations)
  correction-*.md       → decisions/          (QA correction documents)
  briefing-*.md         → daily-briefings/    (morning briefings)
  *                     → raw/ (stays, logged as unclassified)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime, timezone

from src.config import VAULT_DIR

logger = logging.getLogger('daimonion.wiki_ingester')

# Filename pattern → target subdirectory
ROUTING_RULES = [
    (re.compile(r'^synapsis-report-'), 'synapsis-runs'),
    (re.compile(r'^research-'), 'research'),
    (re.compile(r'^correction-'), 'decisions'),
    (re.compile(r'^briefing-'), 'daily-briefings'),
]


def ingest(dry_run: bool = False) -> dict:
    """Process all documents in vault/raw/.

    Args:
        dry_run: If True, report what would happen without moving files.

    Returns:
        Summary dict with counts per destination.
    """
    raw_dir = os.path.join(VAULT_DIR, 'raw')
    if not os.path.isdir(raw_dir):
        return {'processed': 0, 'routes': {}, 'unclassified': []}

    files = [f for f in os.listdir(raw_dir) if f.endswith('.md')]
    if not files:
        return {'processed': 0, 'routes': {}, 'unclassified': []}

    routes: dict[str, list[str]] = {}
    unclassified: list[str] = []

    for fname in sorted(files):
        src_path = os.path.join(raw_dir, fname)
        dest_subdir = _classify(fname)

        if dest_subdir:
            dest_dir = os.path.join(VAULT_DIR, dest_subdir)
            dest_path = os.path.join(dest_dir, fname)

            if not dry_run:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.move(src_path, dest_path)
                logger.info('Ingested: %s → %s/%s', fname, dest_subdir, fname)

            routes.setdefault(dest_subdir, []).append(fname)
        else:
            unclassified.append(fname)
            logger.info('Unclassified (stays in raw/): %s', fname)

    # Update the vault index
    if not dry_run and routes:
        _update_index()

    total = sum(len(v) for v in routes.values())
    logger.info('Wiki ingest: %d routed, %d unclassified', total, len(unclassified))

    return {
        'processed': total,
        'routes': {k: len(v) for k, v in routes.items()},
        'unclassified': unclassified,
    }


def _classify(filename: str) -> str | None:
    """Match filename against routing rules."""
    for pattern, dest in ROUTING_RULES:
        if pattern.match(filename):
            return dest
    return None


def _update_index():
    """Rebuild the vault index.md from current directory contents."""
    index_path = os.path.join(VAULT_DIR, 'index.md')

    sections = {
        'Projects': 'projects',
        'Decisions': 'decisions',
        'Research': 'research',
        'Synapsis Runs': 'synapsis-runs',
        'Daily Briefings': 'daily-briefings',
        'Concepts': 'concepts',
        'Entities': 'entities',
    }

    lines = [
        '# Daimonion Knowledge Vault',
        f'*Auto-generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*',
        '',
    ]

    for section_name, subdir in sections.items():
        subdir_path = os.path.join(VAULT_DIR, subdir)
        if not os.path.isdir(subdir_path):
            continue

        files = sorted(f for f in os.listdir(subdir_path) if f.endswith('.md'))
        if not files:
            continue

        lines.append(f'## {section_name}')
        for fname in files:
            name = fname[:-3]  # strip .md
            display = _display_name(name, subdir)
            lines.append(f'- [[{subdir}/{name}|{display}]]')
        lines.append('')

    with open(index_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    logger.info('Vault index updated: %s', index_path)


def _display_name(name: str, subdir: str) -> str:
    """Generate human-readable display name from filename."""
    if subdir == 'daily-briefings':
        return f'Morning Briefing -- {name}'
    if subdir == 'synapsis-runs':
        # synapsis-report-2026-04-12 → Synapsis Run — 2026-04-12
        date = name.replace('synapsis-report-', '')
        return f'Synapsis Run -- {date}'
    if subdir == 'research':
        return f'Research: {name.replace("-", " ")}'
    # Default: title case with hyphens → spaces
    return name.replace('-', ' ').title()

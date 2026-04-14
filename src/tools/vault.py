"""
Vault Tools — Read/write Obsidian-compatible Markdown wiki.

Atomic writes. Auto wiki-links. Auto index regeneration.
All paths relative to ~/.daimonion/vault/.
"""

import os
import re
from datetime import datetime, timezone

from src.config import VAULT_DIR

LINKABLE_ENTITIES = {
    'Pythia': 'projects/pythia',
    'Graphiti': 'projects/pythia',
    'Daimonion': 'projects/daimonion',
}


def save(path: str, content: str, mode: str = 'update') -> dict:
    """Save a page to the vault.

    Args:
        path: Vault-relative path (e.g. 'projects/nereus.md')
        content: Markdown content
        mode: 'create' (fail if exists), 'update' (overwrite), 'append'
    """
    full = os.path.join(VAULT_DIR, path)

    # Path safety
    if not os.path.realpath(full).startswith(os.path.realpath(VAULT_DIR)):
        return {'status': 'error', 'error': 'Path escapes vault'}

    if mode == 'create' and os.path.exists(full):
        return {'status': 'error', 'error': f'Already exists: {path}'}

    os.makedirs(os.path.dirname(full), exist_ok=True)

    if mode == 'append' and os.path.exists(full):
        with open(full) as f:
            content = f.read().rstrip() + '\n\n' + content

    content = _add_wiki_links(content)

    # Atomic write
    tmp = full + '.tmp'
    with open(tmp, 'w') as f:
        f.write(content)
    os.replace(tmp, full)

    _rebuild_index()
    return {'status': 'ok', 'path': path, 'chars': len(content), 'mode': mode}


def read(path: str) -> dict:
    """Read a vault page."""
    full = os.path.join(VAULT_DIR, path)

    if not os.path.realpath(full).startswith(os.path.realpath(VAULT_DIR)):
        return {'status': 'error', 'error': 'Path escapes vault'}

    if not os.path.exists(full):
        return {'status': 'error', 'error': f'Not found: {path}'}

    with open(full) as f:
        content = f.read()

    return {'status': 'ok', 'path': path, 'content': content, 'chars': len(content)}


def list_dir(subdir: str = '') -> dict:
    """List files in a vault directory."""
    full = os.path.join(VAULT_DIR, subdir)

    if not os.path.realpath(full).startswith(os.path.realpath(VAULT_DIR)):
        return {'status': 'error', 'error': 'Path escapes vault'}

    if not os.path.isdir(full):
        return {'status': 'error', 'error': f'Not a directory: {subdir}'}

    files = []
    for entry in sorted(os.listdir(full)):
        if entry.startswith('.'):
            continue
        entry_path = os.path.join(full, entry)
        if os.path.isdir(entry_path):
            count = len([f for f in os.listdir(entry_path) if f.endswith('.md')])
            files.append({'name': entry + '/', 'type': 'directory', 'files': count})
        elif entry.endswith('.md'):
            files.append({'name': entry, 'type': 'file', 'chars': os.path.getsize(entry_path)})

    return {'status': 'ok', 'directory': subdir or '/', 'files': files, 'count': len(files)}


def _add_wiki_links(text: str) -> str:
    """Insert [[wiki-links]] for known entities."""
    for entity, vault_path in sorted(LINKABLE_ENTITIES.items(), key=lambda x: len(x[0]), reverse=True):
        if entity in text:
            pattern = rf'(?<!\[\[){re.escape(entity)}(?!\]\])'
            text = re.sub(pattern, f'[[{vault_path}|{entity}]]', text, count=1)
    return text


def _rebuild_index():
    """Regenerate vault/index.md."""
    lines = [
        '# Daimonion Knowledge Vault',
        '',
        f'*Auto-generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*',
        '',
    ]

    sections = {
        'projects': 'Projects', 'decisions': 'Decisions', 'research': 'Research',
        'people': 'People', 'daily-briefings': 'Daily Briefings',
    }

    for dirname, title in sections.items():
        dirpath = os.path.join(VAULT_DIR, dirname)
        if not os.path.isdir(dirpath):
            continue
        md_files = sorted(f for f in os.listdir(dirpath) if f.endswith('.md'))
        if not md_files:
            continue

        lines.append(f'## {title}')
        for fname in md_files:
            try:
                with open(os.path.join(dirpath, fname)) as f:
                    first_line = f.readline().strip().lstrip('# ').strip()
            except Exception:
                first_line = fname.replace('.md', '')
            slug = fname.replace('.md', '')
            lines.append(f'- [[{dirname}/{slug}|{first_line}]]')
        lines.append('')

    index_path = os.path.join(VAULT_DIR, 'index.md')
    tmp = index_path + '.tmp'
    with open(tmp, 'w') as f:
        f.write('\n'.join(lines))
    os.replace(tmp, index_path)

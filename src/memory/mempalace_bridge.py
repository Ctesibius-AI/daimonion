"""
mempalace_bridge.py — Bridges wiki and knowledge into MemPalace.

Adds summary drawers to MemPalace for:
1. Wiki pages (source: wiki) — first paragraph as summary
2. Knowledge entries (source: knowledge) — fact text as searchable drawer

This makes MemPalace the unified search interface.
One search returns verbatim conversations + wiki summaries + knowledge facts.
"""

import hashlib
import json
import logging
import os
from datetime import datetime

from mempalace.palace import get_collection

logger = logging.getLogger('daimonion.mempalace_bridge')


def bridge_wiki_page(
    wiki_path: str,
    content: str,
    palace_path: str,
    wing: str = "wiki",
):
    """Add a wiki page summary to MemPalace as a searchable drawer.

    Extracts first paragraph as the summary. Links back to full page.
    """
    collection = get_collection(palace_path)
    if not collection:
        logger.warning('No MemPalace collection — cannot bridge wiki page')
        return

    # Extract first meaningful paragraph as summary
    summary = _extract_summary(content)
    if not summary or len(summary) < 20:
        return

    # Determine room from wiki path
    room = _wiki_path_to_room(wiki_path)

    drawer_id = f"wiki_{hashlib.sha256(wiki_path.encode()).hexdigest()[:24]}"

    try:
        # Upsert so updates replace old summary
        collection.upsert(
            ids=[drawer_id],
            documents=[summary],
            metadatas=[{
                "wing": wing,
                "room": room,
                "hall": "hall_facts",
                "source": "wiki",
                "wiki_path": wiki_path,
                "memory_type": "wiki_summary",
                "added_by": "mempalace_bridge",
                "filed_at": datetime.now().isoformat(),
                "date": datetime.now().strftime("%Y-%m-%d"),
            }],
        )
        logger.info('Wiki bridge: %s → %s/%s', wiki_path, wing, room)
    except Exception as e:
        logger.error('Wiki bridge failed for %s: %s', wiki_path, e)


def bridge_knowledge_entry(
    knowledge: dict,
    palace_path: str,
    wing: str = "knowledge",
):
    """Add a knowledge entry to MemPalace as a searchable drawer.

    The fact text becomes the document, metadata carries the source info.
    """
    collection = get_collection(palace_path)
    if not collection:
        logger.warning('No MemPalace collection — cannot bridge knowledge')
        return

    fact = knowledge.get('fact', knowledge.get('content', ''))
    if not fact or len(fact) < 10:
        return

    kid = knowledge.get('knowledge_id', '')
    category = knowledge.get('category', 'general')
    source_date = knowledge.get('source_date', '')

    drawer_id = f"kb_{hashlib.sha256((kid or fact[:50]).encode()).hexdigest()[:24]}"

    # Map category to room
    room_map = {
        'technical': 'architecture',
        'business': 'business',
        'personal': 'identity',
        'directive': 'philosophy',
    }
    room = room_map.get(category, 'general')

    try:
        collection.upsert(
            ids=[drawer_id],
            documents=[fact],
            metadatas=[{
                "wing": wing,
                "room": room,
                "hall": "hall_facts",
                "source": "knowledge",
                "knowledge_id": kid,
                "category": category,
                "memory_type": "knowledge_fact",
                "added_by": "mempalace_bridge",
                "filed_at": datetime.now().isoformat(),
                "date": source_date or datetime.now().strftime("%Y-%m-%d"),
            }],
        )
        logger.info('Knowledge bridge: %s → %s/%s', kid, wing, room)
    except Exception as e:
        logger.error('Knowledge bridge failed for %s: %s', kid, e)


def bridge_all_knowledge(palace_path: str, knowledge_dir: str):
    """Bridge all existing knowledge entries to MemPalace."""
    if not os.path.isdir(knowledge_dir):
        return 0

    count = 0
    for fname in os.listdir(knowledge_dir):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(knowledge_dir, fname)) as f:
                entry = json.load(f)
            bridge_knowledge_entry(entry, palace_path)
            count += 1
        except (json.JSONDecodeError, IOError):
            continue
    return count


def bridge_all_wiki(palace_path: str, vault_dir: str):
    """Bridge all existing wiki pages to MemPalace."""
    if not os.path.isdir(vault_dir):
        return 0

    count = 0
    for root, _, files in os.walk(vault_dir):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            if fname in ('index.md', 'log.md'):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, vault_dir)

            # Skip raw/ directory
            if rel_path.startswith('raw/'):
                continue

            try:
                with open(full_path) as f:
                    content = f.read()
                bridge_wiki_page(rel_path, content, palace_path)
                count += 1
            except IOError:
                continue
    return count


def _extract_summary(content: str) -> str:
    """Extract first meaningful paragraph from markdown content."""
    lines = content.split('\n')
    paragraph = []
    found_content = False

    for line in lines:
        stripped = line.strip()

        # Skip headers, empty lines, and metadata
        if stripped.startswith('#') or stripped.startswith('*Auto-') or stripped.startswith('---'):
            if found_content and paragraph:
                break
            continue

        if not stripped:
            if found_content and paragraph:
                break
            continue

        found_content = True
        paragraph.append(stripped)

    summary = ' '.join(paragraph)
    if len(summary) > 500:
        summary = summary[:497] + '...'
    return summary


def _wiki_path_to_room(wiki_path: str) -> str:
    """Map wiki directory to a MemPalace room."""
    if wiki_path.startswith('entities/'):
        return 'identity'
    if wiki_path.startswith('concepts/'):
        return 'philosophy'
    if wiki_path.startswith('decisions/'):
        return 'architecture'
    if wiki_path.startswith('projects/'):
        return 'projects'
    if wiki_path.startswith('research/'):
        return 'research'
    if wiki_path.startswith('sources/'):
        return 'research'
    if wiki_path.startswith('synthesis/'):
        return 'research'
    if wiki_path.startswith('daily-briefings/'):
        return 'projects'
    return 'general'

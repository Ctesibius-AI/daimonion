#!/usr/bin/env python3
"""
Pythia Tools — CLI wrappers for Claude Code Pythia to call pipeline functions.

These are the same functions the Telegram/CLI pipeline uses, exposed as
simple command-line tools that Pythia can invoke via Bash.

Usage from Claude Code:
  .venv/bin/python scripts/pythia_tools.py search_memory "What did we decide about the project?"
  .venv/bin/python scripts/pythia_tools.py save_memory "Decided to use Apache 2.0 license" procedural
  .venv/bin/python scripts/pythia_tools.py save_knowledge "Daimonion is Apache 2.0 licensed" business
  .venv/bin/python scripts/pythia_tools.py list_memories
  .venv/bin/python scripts/pythia_tools.py list_knowledge
  .venv/bin/python scripts/pythia_tools.py weather
  .venv/bin/python scripts/pythia_tools.py build_hot_cache
  .venv/bin/python scripts/pythia_tools.py pull_rss
  .venv/bin/python scripts/pythia_tools.py health_check
"""

import json
import os
import sys

sys.path.insert(0, os.path.expanduser('~/daimonion'))


def search_memory(query: str):
    """Semantic search across memories and knowledge using embeddings."""
    import asyncio
    from src.memory.retrieval import create_retriever

    async def _search():
        retriever = create_retriever()
        result = await retriever.retrieve(query, {
            'retrieval_mode': 'general_knowledge',
            'top_k': 5,
        })
        return result

    result = asyncio.run(_search())

    mems = result.get('memory_candidates', [])
    kbs = result.get('knowledge_candidates', [])

    if not mems and not kbs:
        print(f'No results for: "{query}"')
        return

    if mems:
        print('MEMORIES:')
        for m in mems:
            score = m.get('score', 0)
            fact = m.get('fact', '')
            print(f'  [{score:.3f}] {fact}')

    if kbs:
        print('KNOWLEDGE:')
        for k in kbs:
            score = k.get('score', 0)
            fact = k.get('fact', '')
            print(f'  [{score:.3f}] {fact}')


def save_memory(content: str, collection: str = 'episodic', significance: str = 'medium'):
    """Save a memory with proper deduplication and embedding."""
    from src.memory.store import MemoryStore
    from src.memory.embeddings import embed

    store = MemoryStore(embed_fn=embed)
    result = store.save_memory(
        content=content,
        collection=collection,
        source_date=_today(),
    )

    if result:
        print(f'SAVED: {result["id"]} [{collection}]')
        print(f'  {content}')
    else:
        print(f'SKIPPED (duplicate): {content[:80]}')


def save_knowledge(fact: str, category: str = 'technical'):
    """Save a knowledge entry with deduplication."""
    from src.memory.store import MemoryStore
    from src.memory.embeddings import embed

    store = MemoryStore(embed_fn=embed)
    result = store.save_knowledge(
        fact=fact,
        category=category,
    )

    if result:
        print(f'SAVED: {result["id"]} [{category}]')
        print(f'  {fact}')
    else:
        print(f'SKIPPED (duplicate): {fact[:80]}')


def list_memories(collection: str = None):
    """List all active memories."""
    from src.memory.store import MemoryStore
    store = MemoryStore()
    mems = store.list_memories(collection=collection, include_archived=False)
    print(f'{len(mems)} active memories:')
    for m in sorted(mems, key=lambda x: x.get('source_date', ''), reverse=True):
        mid = m.get('memory_id', m.get('id', '?'))
        content = m.get('content', '')[:100]
        col = m.get('collection', '?')
        date = m.get('source_date', '?')
        score = m.get('decay_score', 0)
        print(f'  [{date}] [{col}] (decay:{score:.2f}) {content}')


def list_knowledge(category: str = None):
    """List all knowledge entries."""
    from src.memory.store import MemoryStore
    store = MemoryStore()
    kbs = store.list_knowledge(category=category)
    print(f'{len(kbs)} knowledge entries:')
    for k in sorted(kbs, key=lambda x: x.get('source_date', x.get('created_at', '')), reverse=True):
        kid = k.get('knowledge_id', k.get('id', '?'))
        fact = k.get('fact', k.get('content', ''))[:100]
        cat = k.get('category', '?')
        date = k.get('source_date', '?')
        print(f'  [{date}] [{cat}] {fact}')


def weather(city: str = None):
    """Get weather forecast."""
    from src.tools.weather import get_weather
    print(get_weather(city))


def build_hot_cache():
    """Rebuild the hot cache."""
    from src.core.hot_cache import build_hot_cache as _build
    result = _build()
    print(f'Hot cache rebuilt ({len(result)} chars):')
    print(result)


def pull_rss():
    """Pull RSS feeds and show headlines."""
    try:
        from src.tools.rss_reader import pull_all_categories, get_all_headlines
        pull_all_categories()
        headlines = get_all_headlines(count_per_category=3)
        for cat, items in headlines.items():
            print(f'\n{cat.upper()}:')
            for h in items:
                print(f'  - {h["title"]} ({h["source"]})')
    except ImportError:
        print('feedparser not installed. Run: pip install feedparser')


def health_check():
    """Run system health check."""
    from src.config import (
        MEMORIES_DIR, KNOWLEDGE_DIR, VAULT_DIR, GRAPH_DIR,
        USAGE_DIR, HEALTH_DIR, HOT_CACHE_JSON, RESEARCH_QUEUE_PATH,
    )

    checks = []

    # Memory count
    mem_count = len([f for f in os.listdir(MEMORIES_DIR) if f.endswith('.json')]) if os.path.exists(MEMORIES_DIR) else 0
    checks.append(f'Memories: {mem_count}')

    # Knowledge count
    kb_count = len([f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith('.json')]) if os.path.exists(KNOWLEDGE_DIR) else 0
    checks.append(f'Knowledge: {kb_count}')

    # Vault pages
    vault_pages = 0
    if os.path.exists(VAULT_DIR):
        for root, dirs, files in os.walk(VAULT_DIR):
            vault_pages += sum(1 for f in files if f.endswith('.md'))
    checks.append(f'Vault pages: {vault_pages}')

    # Hot cache
    if os.path.exists(HOT_CACHE_JSON):
        with open(HOT_CACHE_JSON) as f:
            meta = json.load(f)
        checks.append(f'Hot cache: {meta.get("chars", 0)} chars, built {meta.get("built_at", "?")}')
    else:
        checks.append('Hot cache: NOT BUILT')

    # Research queue
    if os.path.exists(RESEARCH_QUEUE_PATH):
        with open(RESEARCH_QUEUE_PATH) as f:
            queue = json.load(f)
        pending = sum(1 for q in queue if q.get('status') == 'pending')
        checks.append(f'Research queue: {pending} pending')
    else:
        checks.append('Research queue: empty')

    # Graph
    if os.path.exists(GRAPH_DIR) and os.listdir(GRAPH_DIR):
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(GRAPH_DIR) for f in fns)
        checks.append(f'Graph DB: {size / 1e6:.1f} MB')
    else:
        checks.append('Graph DB: not initialized')

    # User interests
    interests_path = os.path.expanduser('~/.daimonion/user_interests.json')
    if os.path.exists(interests_path):
        with open(interests_path) as f:
            interests = json.load(f)
        checks.append(f'User interests: {interests.get("topics", [])}')

    print('=== HEALTH CHECK ===')
    for c in checks:
        print(f'  {c}')


def _today():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


COMMANDS = {
    'search_memory': lambda args: search_memory(args[0] if args else 'test'),
    'save_memory': lambda args: save_memory(args[0], args[1] if len(args) > 1 else 'episodic', args[2] if len(args) > 2 else 'medium'),
    'save_knowledge': lambda args: save_knowledge(args[0], args[1] if len(args) > 1 else 'technical'),
    'list_memories': lambda args: list_memories(args[0] if args else None),
    'list_knowledge': lambda args: list_knowledge(args[0] if args else None),
    'weather': lambda args: weather(args[0] if args else None),
    'build_hot_cache': lambda args: build_hot_cache(),
    'pull_rss': lambda args: pull_rss(),
    'health_check': lambda args: health_check(),
}


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f'Usage: pythia_tools.py <command> [args]')
        print(f'Commands: {", ".join(COMMANDS.keys())}')
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]
    COMMANDS[cmd](args)

"""
Pre-synthesized news summary cache.

Cron jobs synthesize conversational news summaries and cache them.
When the user asks for news, serve the cached summary instantly (<100ms).
Only call the LLM at query time if cache is stale or user asks a follow-up.
"""

import json
import os
from datetime import datetime, timezone

from src.config import DATA_DIR

CACHE_DIR = os.path.join(DATA_DIR, 'news', 'cache')


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f'{key}.json')


def save_summary(key: str, summary: str, headlines: list[dict]):
    """Cache a pre-synthesized summary.

    Args:
        key: Cache key (e.g. 'f1', 'sports', 'general', 'morning')
        summary: The synthesized conversational summary
        headlines: The source headlines used (for staleness check)
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    data = {
        'key': key,
        'summary': summary,
        'headline_ids': [h.get('id', '') for h in headlines],
        'synthesized_at': datetime.now(timezone.utc).isoformat(),
    }
    with open(_cache_path(key), 'w') as f:
        json.dump(data, f, indent=2)


def get_summary(key: str) -> dict | None:
    """Get a cached summary. Returns None if not found."""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def is_stale(key: str, current_headline_ids: list[str]) -> bool:
    """Check if the cached summary is stale (headlines have changed)."""
    cached = get_summary(key)
    if not cached:
        return True
    cached_ids = set(cached.get('headline_ids', []))
    current_ids = set(current_headline_ids)
    # Stale if more than half the headlines are new
    if not cached_ids:
        return True
    overlap = cached_ids & current_ids
    return len(overlap) < len(cached_ids) * 0.5


def get_cached_or_none(key: str, current_headlines: list[dict]) -> str | None:
    """Get cached summary if fresh, None if stale or missing.

    This is the main entry point for the orchestrator.
    """
    ids = [h.get('id', '') for h in current_headlines]
    if is_stale(key, ids):
        return None
    cached = get_summary(key)
    if cached:
        return cached['summary']
    return None

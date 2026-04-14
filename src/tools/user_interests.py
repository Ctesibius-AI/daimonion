"""
User interests for personalized news delivery.

Stores a list of topic keywords the user cares about.
Headlines matching these keywords get prioritized in digests.
"""

import json
import os

from src.config import USER_INTERESTS_PATH


def _load() -> dict:
    """Load interests from disk."""
    if not os.path.exists(USER_INTERESTS_PATH):
        return {'topics': []}
    with open(USER_INTERESTS_PATH) as f:
        return json.load(f)


def _save(data: dict):
    """Save interests to disk atomically."""
    os.makedirs(os.path.dirname(USER_INTERESTS_PATH), exist_ok=True)
    tmp = USER_INTERESTS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, USER_INTERESTS_PATH)


def get_interests() -> list[str]:
    """Get the user's tracked topics."""
    return _load().get('topics', [])


def add_interests(topics: list[str]) -> list[str]:
    """Add topics to the user's interests. Returns updated list."""
    data = _load()
    existing = set(t.lower() for t in data.get('topics', []))
    for topic in topics:
        topic = topic.strip()
        if topic and topic.lower() not in existing:
            data.setdefault('topics', []).append(topic)
            existing.add(topic.lower())
    _save(data)
    return data['topics']


def remove_interests(topics: list[str]) -> list[str]:
    """Remove topics from the user's interests. Returns updated list."""
    data = _load()
    remove_lower = set(t.strip().lower() for t in topics)
    data['topics'] = [t for t in data.get('topics', []) if t.lower() not in remove_lower]
    _save(data)
    return data['topics']


def matches_interests(text: str, interests: list[str] | None = None) -> list[str]:
    """Check which interests match a given text. Returns list of matched topics."""
    if interests is None:
        interests = get_interests()
    text_lower = text.lower()
    return [topic for topic in interests if topic.lower() in text_lower]

"""
Research Queue — Bridge between daytime flagging and nighttime research.

Two sources: daytime web_search flags + Synapsis Analyze step flags.
Synapsis reads, deduplicates, picks max 3 per night.
"""

import json
import os
from datetime import datetime, timezone

from src.config import RESEARCH_QUEUE_PATH, MAX_RESEARCH_TOPICS_PER_NIGHT


def flag_for_research(topic: str, reason: str, source: str = 'daytime') -> dict:
    """Add a topic to the overnight research queue."""
    queue = _load()

    for item in queue:
        if item['topic'].lower() == topic.lower() and item['status'] == 'pending':
            return {'status': 'duplicate', 'message': f'Already queued: {topic}'}

    queue.append({
        'topic': topic,
        'reason': reason,
        'source': source,
        'flagged_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pending',
    })

    _save(queue)
    pending = sum(1 for q in queue if q['status'] == 'pending')
    return {'status': 'ok', 'message': f'Flagged for research: {topic}', 'pending': pending}


def get_pending(max_topics: int = MAX_RESEARCH_TOPICS_PER_NIGHT) -> list[dict]:
    """Get pending topics. Synapsis calls this."""
    queue = _load()
    pending = [q for q in queue if q['status'] == 'pending']
    pending.sort(key=lambda q: q.get('flagged_at', ''), reverse=True)
    return pending[:max_topics]


def mark_researched(topic: str) -> dict:
    """Mark topic as completed."""
    queue = _load()
    for item in queue:
        if item['topic'].lower() == topic.lower() and item['status'] == 'pending':
            item['status'] = 'completed'
            item['completed_at'] = datetime.now(timezone.utc).isoformat()
            _save(queue)
            return {'status': 'ok', 'message': f'Marked researched: {topic}'}
    return {'status': 'not_found', 'message': f'Not found: {topic}'}


def _load() -> list[dict]:
    if not os.path.exists(RESEARCH_QUEUE_PATH):
        return []
    try:
        with open(RESEARCH_QUEUE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save(queue: list[dict]):
    os.makedirs(os.path.dirname(RESEARCH_QUEUE_PATH), exist_ok=True)
    tmp = RESEARCH_QUEUE_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(queue, f, indent=2)
    os.replace(tmp, RESEARCH_QUEUE_PATH)

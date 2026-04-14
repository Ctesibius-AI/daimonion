"""
Unit tests for the research queue.

Tests flagging, deduplication, retrieval, marking as researched.
"""

import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def queue(tmp_path):
    queue_path = str(tmp_path / 'research_queue.json')
    with patch('src.config.RESEARCH_QUEUE_PATH', queue_path):
        # Re-import to pick up patched path
        import importlib
        import src.tools.research_queue as rq_mod
        importlib.reload(rq_mod)
        yield {
            'flag': rq_mod.flag_for_research,
            'get': rq_mod.get_pending,
            'mark': rq_mod.mark_researched,
            'path': queue_path,
        }
        # Reload back to original
        importlib.reload(rq_mod)


class TestFlagging:
    def test_flag_new_topic(self, queue):
        result = queue['flag']('AI regulation EU', 'Mentioned in conversation')
        assert result['status'] == 'ok'
        assert result['pending'] == 1

    def test_flag_multiple_topics(self, queue):
        queue['flag']('Topic 1', 'reason 1')
        result = queue['flag']('Topic 2', 'reason 2')
        assert result['pending'] == 2

    def test_duplicate_blocked(self, queue):
        queue['flag']('AI regulation', 'reason')
        result = queue['flag']('AI regulation', 'different reason')
        assert result['status'] == 'duplicate'

    def test_duplicate_case_insensitive(self, queue):
        queue['flag']('AI Regulation', 'reason')
        result = queue['flag']('ai regulation', 'reason')
        assert result['status'] == 'duplicate'

    def test_source_recorded(self, queue):
        queue['flag']('test', 'reason', source='night_analyzer')
        with open(queue['path']) as f:
            data = json.load(f)
        assert data[0]['source'] == 'night_analyzer'

    def test_timestamp_recorded(self, queue):
        queue['flag']('test', 'reason')
        with open(queue['path']) as f:
            data = json.load(f)
        assert 'flagged_at' in data[0]


class TestRetrieval:
    def test_get_pending(self, queue):
        queue['flag']('Topic 1', 'r1')
        queue['flag']('Topic 2', 'r2')
        pending = queue['get']()
        assert len(pending) == 2

    def test_max_topics_respected(self, queue):
        for i in range(5):
            queue['flag'](f'Topic {i}', f'reason {i}')
        pending = queue['get'](max_topics=3)
        assert len(pending) == 3

    def test_most_recent_first(self, queue):
        queue['flag']('Old topic', 'old')
        queue['flag']('New topic', 'new')
        pending = queue['get']()
        assert pending[0]['topic'] == 'New topic'

    def test_completed_excluded(self, queue):
        queue['flag']('Done', 'reason')
        queue['mark']('Done')
        pending = queue['get']()
        assert len(pending) == 0

    def test_empty_queue(self, queue):
        assert queue['get']() == []


class TestMarkResearched:
    def test_marks_as_completed(self, queue):
        queue['flag']('test', 'reason')
        result = queue['mark']('test')
        assert result['status'] == 'ok'
        with open(queue['path']) as f:
            data = json.load(f)
        assert data[0]['status'] == 'completed'
        assert 'completed_at' in data[0]

    def test_mark_nonexistent(self, queue):
        result = queue['mark']('nonexistent')
        assert result['status'] == 'not_found'

    def test_mark_case_insensitive(self, queue):
        queue['flag']('AI Regulation', 'reason')
        result = queue['mark']('ai regulation')
        assert result['status'] == 'ok'


class TestPersistence:
    def test_survives_reload(self, queue, tmp_path):
        queue['flag']('test', 'reason')
        # Verify data persisted to disk
        assert os.path.exists(queue['path'])
        with open(queue['path']) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_handles_corrupt_file(self, queue):
        with open(queue['path'], 'w') as f:
            f.write('not json')
        # Should recover gracefully
        result = queue['flag']('test', 'reason')
        assert result['status'] == 'ok'

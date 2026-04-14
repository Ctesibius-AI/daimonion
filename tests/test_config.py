"""
Unit tests for Daimonion configuration.

Verifies all paths are correct, directories are created, and constants are valid.
"""

import os

import pytest

from src.config import (
    DATA_DIR, MEMORIES_DIR, KNOWLEDGE_DIR, GRAPH_DIR, VAULT_DIR,
    CONVERSATIONS_DIR, DAILY_LOG_DIR, USAGE_DIR, HEALTH_DIR, SESSIONS_DIR,
    NIGHT_RUNS_DIR, HOT_CACHE_MD, HOT_CACHE_JSON, RESEARCH_QUEUE_PATH,
    PROJECT_DIR, SKILLS_DIR, SOUL_SONNET_PATH, SOUL_OPUS_PATH,
    SKILL_INDEX_PATH, BASELINE_PATTERNS_PATH,
    SONNET_MODEL, OPUS_MODEL, HAIKU_MODEL,
    DEFAULT_CITY, MAX_RESEARCH_TOPICS_PER_NIGHT,
    MEMORY_ARCHIVE_THRESHOLD, DEDUP_SIMILARITY_THRESHOLD,
    CONVERSATION_MAX_TOKENS,
)


class TestDataPaths:
    def test_data_dir_is_home_daimonion(self):
        assert DATA_DIR == os.path.expanduser('~/.daimonion')

    def test_all_data_subdirs_exist(self):
        for d in [MEMORIES_DIR, KNOWLEDGE_DIR, GRAPH_DIR, VAULT_DIR,
                  CONVERSATIONS_DIR, DAILY_LOG_DIR, USAGE_DIR, HEALTH_DIR,
                  SESSIONS_DIR, NIGHT_RUNS_DIR]:
            assert os.path.isdir(d), f'Missing directory: {d}'

    def test_paths_are_under_data_dir(self):
        for path in [MEMORIES_DIR, KNOWLEDGE_DIR, GRAPH_DIR, VAULT_DIR,
                     CONVERSATIONS_DIR, USAGE_DIR, HEALTH_DIR, SESSIONS_DIR]:
            assert path.startswith(DATA_DIR)

    def test_hot_cache_paths(self):
        assert HOT_CACHE_MD.endswith('hot_cache.md')
        assert HOT_CACHE_JSON.endswith('hot_cache.json')

    def test_research_queue_path(self):
        assert RESEARCH_QUEUE_PATH.endswith('research_queue.json')


class TestProjectPaths:
    def test_project_dir_exists(self):
        assert os.path.isdir(PROJECT_DIR)

    def test_skills_dir_exists(self):
        assert os.path.isdir(SKILLS_DIR)

    def test_soul_paths_point_to_identity(self):
        assert 'identity' in SOUL_SONNET_PATH
        assert 'identity' in SOUL_OPUS_PATH

    def test_skill_index_path(self):
        assert 'meta' in SKILL_INDEX_PATH
        assert SKILL_INDEX_PATH.endswith('.yaml')

    def test_baseline_patterns_path(self):
        assert 'context' in BASELINE_PATTERNS_PATH


class TestModels:
    def test_sonnet_model(self):
        assert 'sonnet' in SONNET_MODEL

    def test_opus_model(self):
        assert 'opus' in OPUS_MODEL

    def test_haiku_model(self):
        assert 'haiku' in HAIKU_MODEL


class TestConstants:
    def test_default_city(self):
        assert DEFAULT_CITY == 'Athens'

    def test_max_research_topics(self):
        assert MAX_RESEARCH_TOPICS_PER_NIGHT == 3

    def test_archive_threshold(self):
        assert 0 < MEMORY_ARCHIVE_THRESHOLD < 1

    def test_dedup_threshold(self):
        assert 0 < DEDUP_SIMILARITY_THRESHOLD < 1

    def test_conversation_max_tokens(self):
        assert CONVERSATION_MAX_TOKENS > 0


class TestNoLegacyRefs:
    """Verify no legacy references leaked into config."""

    def test_no_legacy_in_data_dir(self):
        assert 'openclaw' not in DATA_DIR.lower()

    def test_no_legacy_in_any_path(self):
        paths = [MEMORIES_DIR, KNOWLEDGE_DIR, GRAPH_DIR, VAULT_DIR,
                 CONVERSATIONS_DIR, USAGE_DIR, HEALTH_DIR, SESSIONS_DIR,
                 HOT_CACHE_MD, RESEARCH_QUEUE_PATH]
        for p in paths:
            assert 'openclaw' not in p.lower(), f'Legacy reference in: {p}'

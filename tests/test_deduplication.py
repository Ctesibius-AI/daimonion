"""
Unit tests for write-time deduplication and supersession detection.

Uses synthetic embeddings — no model loading needed.
"""

from datetime import datetime, timezone, timedelta

import numpy as np
import pytest

from src.memory.decay import MemoryRecord
from src.memory.deduplication import (
    DEDUP_THRESHOLD,
    SUPERSESSION_THRESHOLD,
    Deduplicator,
    SupersessionDetector,
    cosine_similarity,
)


def _make_vec(dim=384, seed=None):
    """Random unit vector."""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def _make_similar_vec(base: list[float], similarity: float, seed=42):
    """Create a vector with a target cosine similarity to base."""
    rng = np.random.RandomState(seed)
    base_arr = np.array(base)
    ortho = rng.randn(len(base))
    ortho = ortho - np.dot(ortho, base_arr) * base_arr
    ortho = ortho / np.linalg.norm(ortho)
    vec = similarity * base_arr + np.sqrt(1 - similarity ** 2) * ortho
    return (vec / np.linalg.norm(vec)).tolist()


def _mem_record(memory_id='mem_001', days_old=30):
    created = datetime(2026, 6, 30, tzinfo=timezone.utc) - timedelta(days=days_old)
    return MemoryRecord(
        memory_id=memory_id,
        content='test content',
        created_at=created,
    )


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = _make_vec(seed=1)
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0, abs=0.001)

    def test_opposite_vectors(self):
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0, abs=0.001)

    def test_zero_vector_returns_0(self):
        assert cosine_similarity([1, 2], [0, 0]) == 0.0

    def test_similar_vectors_high_score(self):
        base = _make_vec(seed=1)
        similar = _make_similar_vec(base, 0.95)
        assert cosine_similarity(base, similar) == pytest.approx(0.95, abs=0.01)


class TestDeduplication:
    def test_duplicate_blocked(self):
        base = _make_vec(seed=1)
        dup = _make_similar_vec(base, 0.90)
        dedup = Deduplicator(embed_fn=None)
        ok, dup_id = dedup.should_write('test', base, [('mem_001', dup)])
        assert ok is False
        assert dup_id == 'mem_001'

    def test_unique_content_allowed(self):
        a = _make_vec(seed=1)
        b = _make_vec(seed=2)
        dedup = Deduplicator(embed_fn=None)
        ok, dup_id = dedup.should_write('test', a, [('mem_001', b)])
        assert ok is True
        assert dup_id is None

    def test_threshold_boundary_above(self):
        base = _make_vec(seed=1)
        just_above = _make_similar_vec(base, DEDUP_THRESHOLD + 0.01)
        dedup = Deduplicator(embed_fn=None)
        ok, _ = dedup.should_write('test', base, [('mem_001', just_above)])
        assert ok is False

    def test_threshold_boundary_below(self):
        base = _make_vec(seed=1)
        just_below = _make_similar_vec(base, DEDUP_THRESHOLD - 0.03)
        dedup = Deduplicator(embed_fn=None)
        ok, _ = dedup.should_write('test', base, [('mem_001', just_below)])
        assert ok is True

    def test_empty_existing_always_writes(self):
        dedup = Deduplicator(embed_fn=None)
        ok, dup_id = dedup.should_write('test', _make_vec(seed=1), [])
        assert ok is True
        assert dup_id is None


class TestSupersessionDetector:
    def test_detects_supersession(self):
        detector = SupersessionDetector()
        old = _mem_record('mem_old', days_old=60)
        new = _mem_record('mem_new', days_old=0)
        base = _make_vec(seed=1)
        similar = _make_similar_vec(base, 0.90)
        result = detector.detect(new, base, [(old, similar)])
        assert 'mem_old' in result

    def test_no_supersession_for_older_new_memory(self):
        detector = SupersessionDetector()
        old = _mem_record('mem_old', days_old=0)
        new = _mem_record('mem_new', days_old=60)
        base = _make_vec(seed=1)
        similar = _make_similar_vec(base, 0.90)
        assert detector.detect(new, base, [(old, similar)]) == []

    def test_no_supersession_for_low_similarity(self):
        detector = SupersessionDetector()
        old = _mem_record('mem_old', days_old=60)
        new = _mem_record('mem_new', days_old=0)
        a = _make_vec(seed=1)
        b = _make_vec(seed=2)
        assert detector.detect(new, a, [(old, b)]) == []

    def test_skips_self(self):
        detector = SupersessionDetector()
        mem = _mem_record('mem_001', days_old=30)
        base = _make_vec(seed=1)
        assert detector.detect(mem, base, [(mem, base)]) == []

    def test_multiple_supersessions(self):
        detector = SupersessionDetector()
        new = _mem_record('mem_new', days_old=0)
        old1 = _mem_record('mem_old1', days_old=60)
        old2 = _mem_record('mem_old2', days_old=90)
        base = _make_vec(seed=1)
        sim1 = _make_similar_vec(base, 0.90, seed=10)
        sim2 = _make_similar_vec(base, 0.88, seed=20)
        result = detector.detect(new, base, [(old1, sim1), (old2, sim2)])
        assert 'mem_old1' in result
        assert 'mem_old2' in result

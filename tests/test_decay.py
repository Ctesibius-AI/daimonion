"""
Unit tests for the decay scoring system.

Tests the decay formula (time x access x correction), per-collection rates,
archive detection, and bulk scoring. No API calls — pure math.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.memory.decay import (
    ARCHIVE_THRESHOLD,
    DECAY_RATES,
    MIN_ARCHIVE_AGE_DAYS,
    DecayScorer,
    MemoryRecord,
)


@pytest.fixture
def scorer():
    return DecayScorer()


def _mem(collection='episodic', days_old=0, access_count=0,
         last_accessed_days_ago=None, correction_factor=1.0):
    """Helper to build a MemoryRecord at a known age."""
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    created = now - timedelta(days=days_old)
    last_accessed = None
    if last_accessed_days_ago is not None:
        last_accessed = now - timedelta(days=last_accessed_days_ago)
    return MemoryRecord(
        memory_id='mem_test',
        content='test memory',
        collection=collection,
        created_at=created,
        access_count=access_count,
        last_accessed=last_accessed,
        correction_factor=correction_factor,
    ), now


class TestTimeFactor:
    def test_fresh_memory_has_full_time_factor(self, scorer):
        mem, now = _mem(days_old=0)
        score = scorer.calculate(mem, now)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_identity_decays_slowly(self, scorer):
        time_factor = DECAY_RATES['identity'] ** 365
        assert time_factor == pytest.approx(0.694, abs=0.01)

    def test_episodic_decays_fast(self, scorer):
        time_factor = DECAY_RATES['episodic'] ** 365
        assert time_factor == pytest.approx(0.004, abs=0.002)

    def test_sessions_decay_fastest(self, scorer):
        time_factor = DECAY_RATES['sessions'] ** 90
        assert time_factor < 0.03

    @pytest.mark.parametrize('collection', DECAY_RATES.keys())
    def test_all_collections_have_valid_rates(self, collection):
        rate = DECAY_RATES[collection]
        assert 0 < rate < 1


class TestAccessFactor:
    def test_no_access_gives_base_0_5(self, scorer):
        mem, now = _mem(days_old=0, access_count=0)
        score = scorer.calculate(mem, now)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_access_count_boosts_score(self, scorer):
        mem_0, now = _mem(days_old=0, access_count=0)
        mem_3, _ = _mem(days_old=0, access_count=3)
        assert scorer.calculate(mem_3, now) > scorer.calculate(mem_0, now)

    def test_access_contribution_caps_at_0_3(self, scorer):
        mem_3, now = _mem(days_old=0, access_count=3)
        mem_100, _ = _mem(days_old=0, access_count=100)
        assert scorer.calculate(mem_100, now) >= scorer.calculate(mem_3, now)

    def test_recent_access_gives_recency_boost(self, scorer):
        mem_old, now = _mem(days_old=30, access_count=2, last_accessed_days_ago=60)
        mem_recent, _ = _mem(days_old=30, access_count=2, last_accessed_days_ago=3)
        assert scorer.calculate(mem_recent, now) > scorer.calculate(mem_old, now)

    def test_access_within_7_days_gives_0_2_boost(self, scorer):
        mem_no, now = _mem(days_old=0, access_count=0)
        mem_recent, _ = _mem(days_old=0, access_count=0, last_accessed_days_ago=3)
        diff = scorer.calculate(mem_recent, now) - scorer.calculate(mem_no, now)
        assert diff == pytest.approx(0.2, abs=0.01)

    def test_access_factor_capped_at_1_0(self, scorer):
        mem, now = _mem(days_old=0, access_count=10, last_accessed_days_ago=1)
        assert scorer.calculate(mem, now) <= 1.0


class TestCorrectionFactor:
    def test_superseded_drops_to_30_percent(self, scorer):
        mem_curr, now = _mem(days_old=30, correction_factor=1.0)
        mem_super, _ = _mem(days_old=30, correction_factor=0.3)
        score_curr = scorer.calculate(mem_curr, now)
        score_super = scorer.calculate(mem_super, now)
        assert score_super == pytest.approx(score_curr * 0.3, abs=0.01)

    def test_corrected_drops_to_10_percent(self, scorer):
        mem_curr, now = _mem(days_old=30, correction_factor=1.0)
        mem_corr, _ = _mem(days_old=30, correction_factor=0.1)
        score_curr = scorer.calculate(mem_curr, now)
        score_corr = scorer.calculate(mem_corr, now)
        assert score_corr == pytest.approx(score_curr * 0.1, abs=0.01)


class TestArchiveDetection:
    def test_fresh_memory_never_archived(self, scorer):
        mem, now = _mem(days_old=1)
        assert scorer.should_archive(mem, now) is False

    def test_old_low_score_gets_archived(self, scorer):
        mem, now = _mem(collection='episodic', days_old=180, correction_factor=0.3)
        assert scorer.should_archive(mem, now) is True

    def test_min_age_respected(self, scorer):
        mem, now = _mem(collection='sessions', days_old=30, correction_factor=0.1)
        score = scorer.calculate(mem, now)
        assert score < ARCHIVE_THRESHOLD
        assert scorer.should_archive(mem, now) is False

    def test_high_score_never_archived(self, scorer):
        mem, now = _mem(collection='identity', days_old=365, access_count=5,
                        last_accessed_days_ago=2)
        assert scorer.should_archive(mem, now) is False

    def test_session_archives_after_min_age(self, scorer):
        mem, now = _mem(collection='sessions', days_old=90)
        assert scorer.should_archive(mem, now) is True


class TestBulkScoring:
    def test_scores_multiple_memories(self, scorer):
        now = datetime(2026, 6, 30, tzinfo=timezone.utc)
        memories = [
            MemoryRecord(memory_id=f'mem_{i}', content=f'test {i}',
                         created_at=now - timedelta(days=i * 30))
            for i in range(5)
        ]
        results = scorer.bulk_score(memories, now)
        assert len(results) == 5
        for mem, score, archive in results:
            assert 0 <= score <= 1
            assert isinstance(archive, bool)

    def test_newer_memories_score_higher(self, scorer):
        now = datetime(2026, 6, 30, tzinfo=timezone.utc)
        memories = [
            MemoryRecord(memory_id='new', content='new', collection='episodic',
                         created_at=now - timedelta(days=7)),
            MemoryRecord(memory_id='old', content='old', collection='episodic',
                         created_at=now - timedelta(days=180)),
        ]
        results = scorer.bulk_score(memories, now)
        assert results[0][1] > results[1][1]


class TestScoreInvariants:
    def test_score_always_between_0_and_1(self, scorer):
        now = datetime(2026, 6, 30, tzinfo=timezone.utc)
        cases = [
            _mem(days_old=0)[0],
            _mem(days_old=365, access_count=100, last_accessed_days_ago=1)[0],
            _mem(days_old=1000, correction_factor=0.1)[0],
            _mem(collection='sessions', days_old=365)[0],
        ]
        for mem in cases:
            score = scorer.calculate(mem, now)
            assert 0 <= score <= 1, f'Score {score} out of range'

    def test_score_monotonically_decreases_with_age(self, scorer):
        now = datetime(2026, 6, 30, tzinfo=timezone.utc)
        prev_score = 1.0
        for days in [0, 30, 60, 90, 180, 365]:
            mem = MemoryRecord(
                memory_id='test', content='test', collection='episodic',
                created_at=now - timedelta(days=days),
            )
            score = scorer.calculate(mem, now)
            assert score <= prev_score
            prev_score = score

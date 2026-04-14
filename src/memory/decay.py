"""
Decay scoring system for Daimonion memories.

Every memory has a decay score in [0.0, 1.0]:

    decay_score = time_factor x access_factor x correction_factor

- time_factor: exponential decay per collection type
- access_factor: frequently retrieved memories resist decay
- correction_factor: superseded memories drop sharply (0.3 or 0.1)

When decay_score drops below ARCHIVE_THRESHOLD (0.05) and the memory
is older than MIN_ARCHIVE_AGE_DAYS (60), it is archived -- never deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Per-collection exponential decay rates (applied daily)
# Higher = slower decay. All in [0, 1].
DECAY_RATES = {
    'identity': 0.999,      # Personal traits -- almost permanent (0.69 after 1 year)
    'procedural': 0.997,    # Technical decisions -- months-relevant (0.33 after 1 year)
    'insights': 0.993,      # Strategic observations -- medium lifespan (0.08 after 1 year)
    'episodic': 0.985,      # Specific events -- fades faster (0.004 after 1 year)
    'sessions': 0.960,      # Conversation summaries -- short-lived (~0 after 3 months)
}

DEFAULT_DECAY_RATE = 0.990

ARCHIVE_THRESHOLD = 0.05
MIN_ARCHIVE_AGE_DAYS = 60


@dataclass
class MemoryRecord:
    """Minimal memory record for decay scoring.

    Lightweight representation -- the full memory document lives in JSON
    files or Graphiti. This only holds the fields decay scoring needs.
    """
    memory_id: str
    content: str
    collection: str = 'episodic'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    last_accessed: datetime | None = None
    correction_factor: float = 1.0  # 1.0=current, 0.3=superseded, 0.1=corrected
    decay_score: float = 1.0
    archived: bool = False


class DecayScorer:
    """Calculates decay scores for memory records.

    decay_score = time_factor x access_factor x correction_factor
    """

    def calculate(self, memory: MemoryRecord, now: datetime | None = None) -> float:
        """Calculate the current decay score for a memory."""
        now = now or datetime.now(timezone.utc)
        days = max(0, (now - memory.created_at).total_seconds() / 86400)

        time_factor = self._time_factor(days, memory.collection)
        access_factor = self._access_factor(memory, now)
        correction_factor = memory.correction_factor

        return time_factor * access_factor * correction_factor

    def should_archive(self, memory: MemoryRecord, now: datetime | None = None) -> bool:
        """Check if a memory should be archived. Never delete -- only archive."""
        now = now or datetime.now(timezone.utc)
        score = self.calculate(memory, now)
        days = (now - memory.created_at).total_seconds() / 86400
        return score < ARCHIVE_THRESHOLD and days > MIN_ARCHIVE_AGE_DAYS

    def bulk_score(
        self, memories: list[MemoryRecord], now: datetime | None = None
    ) -> list[tuple[MemoryRecord, float, bool]]:
        """Score a batch of memories. Returns list of (memory, score, should_archive)."""
        now = now or datetime.now(timezone.utc)
        results = []
        for mem in memories:
            score = self.calculate(mem, now)
            archive = score < ARCHIVE_THRESHOLD and (
                (now - mem.created_at).total_seconds() / 86400 > MIN_ARCHIVE_AGE_DAYS
            )
            results.append((mem, score, archive))
        return results

    def _time_factor(self, days: float, collection: str) -> float:
        """Exponential time decay per collection type."""
        rate = DECAY_RATES.get(collection, DEFAULT_DECAY_RATE)
        return rate ** days

    def _access_factor(self, memory: MemoryRecord, now: datetime) -> float:
        """Access-based decay resistance.

        Frequently retrieved memories resist decay. Recent access gives a boost.
        Base of 0.5 means an untouched memory starts halfway penalized.
        """
        # Base + access count contribution (capped at 0.3)
        access_contribution = min(memory.access_count * 0.1, 0.3)

        # Recency boost based on last access
        recency_boost = 0.0
        if memory.last_accessed is not None:
            days_since_access = (now - memory.last_accessed).total_seconds() / 86400
            if days_since_access <= 7:
                recency_boost = 0.2
            elif days_since_access <= 30:
                recency_boost = 0.1

        return min(1.0, 0.5 + access_contribution + recency_boost)

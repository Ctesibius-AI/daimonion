"""
Write-time deduplication and supersession detection for Daimonion memories.

Deduplication:
  Before writing a new memory, check semantic similarity against existing
  memories. If similarity > DEDUP_THRESHOLD (0.82), skip the write.

Supersession:
  When a new memory is written that is semantically similar to an existing
  memory but from a later date, the old memory's correction_factor drops
  to 0.3 (superseded). Both are preserved -- nothing is deleted.
"""

from __future__ import annotations

import numpy as np

from src.memory.decay import MemoryRecord

DEDUP_THRESHOLD = 0.82
SUPERSESSION_THRESHOLD = 0.82


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class Deduplicator:
    """Write-time deduplication against existing memories."""

    def __init__(self, embed_fn):
        """Args:
            embed_fn: Callable that takes a string and returns a list[float] embedding.
        """
        self.embed = embed_fn

    def should_write(
        self,
        new_content: str,
        new_embedding: list[float],
        existing_embeddings: list[tuple[str, list[float]]],
    ) -> tuple[bool, str | None]:
        """Check if a new memory should be written or is a duplicate.

        Args:
            new_content: The text of the new memory.
            new_embedding: Pre-computed embedding of the new memory.
            existing_embeddings: List of (memory_id, embedding) for existing memories.

        Returns:
            (should_write, duplicate_id) -- True if new, False if duplicate.
            duplicate_id is the ID of the matching existing memory, or None.
        """
        for mem_id, existing_emb in existing_embeddings:
            sim = cosine_similarity(new_embedding, existing_emb)
            if sim >= DEDUP_THRESHOLD:
                return False, mem_id

        return True, None


class SupersessionDetector:
    """Detect when a new memory supersedes an existing one.

    A supersession occurs when:
      1. New memory is semantically similar (>0.82) to an existing memory
      2. New memory is from a later date
      3. Content is different enough to represent updated information

    The old memory's correction_factor drops to 0.3 -- it's preserved
    but deprioritized in retrieval.
    """

    def detect(
        self,
        new_memory: MemoryRecord,
        new_embedding: list[float],
        existing_memories: list[tuple[MemoryRecord, list[float]]],
    ) -> list[str]:
        """Find existing memories that the new one supersedes.

        Args:
            new_memory: The newly written memory record.
            new_embedding: Pre-computed embedding of the new memory.
            existing_memories: List of (MemoryRecord, embedding) to check against.

        Returns:
            List of memory_ids that should have correction_factor set to 0.3.
        """
        superseded_ids = []

        for existing, existing_emb in existing_memories:
            # Skip self
            if existing.memory_id == new_memory.memory_id:
                continue

            # Must be from an earlier date
            if existing.created_at >= new_memory.created_at:
                continue

            # Check semantic similarity
            sim = cosine_similarity(new_embedding, existing_emb)
            if sim >= SUPERSESSION_THRESHOLD:
                # High similarity + different date = supersession
                superseded_ids.append(existing.memory_id)

        return superseded_ids

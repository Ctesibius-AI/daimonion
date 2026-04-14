"""
Memory storage layer for Daimonion.

Saves episodic memories and factual knowledge as JSON files with:
- Deduplication before writing (via Deduplicator)
- Supersession detection (via SupersessionDetector)
- Decay scoring (via DecayScorer)
- Atomic writes (tmp + os.replace)
- Never deletes -- only archives

Memory JSON schema:
    id, content, collection, created_at, source_date, source_conversation_date,
    access_count, last_accessed, correction_factor, decay_score, archived,
    embedding (list[float])

Knowledge JSON schema:
    id, fact, category, source_memories (list of memory ids),
    created_at, confidence
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

from src.config import KNOWLEDGE_DIR, MEMORIES_DIR
from src.memory.decay import DecayScorer, MemoryRecord
from src.memory.deduplication import Deduplicator, SupersessionDetector


class MemoryStore:
    """Persistent store for episodic memories and factual knowledge.

    All writes are atomic (write to tmpfile, then os.replace).
    All deletions are forbidden -- use archive_memory() instead.
    """

    def __init__(self, embed_fn=None):
        """Initialize the store.

        Args:
            embed_fn: Callable(str) -> list[float]. If None, uses
                      src.memory.embeddings.embed (lazy loaded).
        """
        if embed_fn is None:
            from src.memory.embeddings import embed
            self._embed = embed
        else:
            self._embed = embed_fn

        self._scorer = DecayScorer()
        self._deduplicator = Deduplicator(self._embed)
        self._supersession = SupersessionDetector()

        os.makedirs(MEMORIES_DIR, exist_ok=True)
        os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

    # ─── Memory Operations ──────────────────────────────────────────

    def save_memory(
        self,
        content: str,
        collection: str = 'episodic',
        source_date: str | None = None,
        source_conversation_date: str | None = None,
        correction_factor: float = 1.0,
    ) -> dict | None:
        """Save an episodic memory to disk.

        Runs deduplication and supersession detection before writing.
        Returns the saved memory dict, or None if it was a duplicate.
        """
        # Compute embedding
        embedding = self._embed(content)

        # Load existing embeddings for dedup check
        existing_embeddings = self._load_memory_embeddings()

        # Deduplication
        should_write, duplicate_id = self._deduplicator.should_write(
            content, embedding, existing_embeddings,
        )
        if not should_write:
            return None

        # Build memory record
        now = datetime.now(timezone.utc)
        memory_id = str(uuid.uuid4())

        memory = {
            'id': memory_id,
            'content': content,
            'collection': collection,
            'created_at': now.isoformat(),
            'source_date': source_date,
            'source_conversation_date': source_conversation_date,
            'access_count': 0,
            'last_accessed': None,
            'correction_factor': correction_factor,
            'decay_score': 1.0,
            'archived': False,
            'embedding': embedding,
        }

        # Atomic write
        self._atomic_write(
            os.path.join(MEMORIES_DIR, f'{memory_id}.json'),
            memory,
        )

        # Supersession detection
        self._check_supersession(memory, embedding)

        return memory

    def get_memory(self, memory_id: str) -> dict | None:
        """Load a single memory by ID."""
        fpath = os.path.join(MEMORIES_DIR, f'{memory_id}.json')
        if not os.path.exists(fpath):
            return None
        try:
            with open(fpath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def list_memories(
        self,
        collection: str | None = None,
        include_archived: bool = False,
    ) -> list[dict]:
        """List all memories, optionally filtered by collection.

        Archived memories are excluded by default.
        """
        memories = []
        if not os.path.isdir(MEMORIES_DIR):
            return memories

        for fname in os.listdir(MEMORIES_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(MEMORIES_DIR, fname)
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            if not include_archived and data.get('archived', False):
                continue
            if collection and data.get('collection') != collection:
                continue

            memories.append(data)

        return memories

    def archive_memory(self, memory_id: str) -> bool:
        """Archive a memory. Never deletes -- sets archived=True."""
        mem = self.get_memory(memory_id)
        if mem is None:
            return False

        mem['archived'] = True
        self._atomic_write(
            os.path.join(MEMORIES_DIR, f'{memory_id}.json'),
            mem,
        )
        return True

    def update_access(self, memory_id: str) -> bool:
        """Record that a memory was accessed (retrieved).

        Increments access_count and updates last_accessed.
        Also recalculates the decay score.
        """
        mem = self.get_memory(memory_id)
        if mem is None:
            return False

        now = datetime.now(timezone.utc)
        mem['access_count'] = mem.get('access_count', 0) + 1
        mem['last_accessed'] = now.isoformat()

        # Recalculate decay score
        record = self._to_record(mem)
        mem['decay_score'] = self._scorer.calculate(record, now)

        self._atomic_write(
            os.path.join(MEMORIES_DIR, f'{memory_id}.json'),
            mem,
        )
        return True

    # ─── Knowledge Operations ───────────────────────────────────────

    def save_knowledge(
        self,
        fact: str,
        category: str = 'general',
        source_memories: list[str] | None = None,
        confidence: float = 1.0,
    ) -> dict | None:
        """Save a factual knowledge entry to disk.

        Runs deduplication against existing knowledge before writing.
        Returns the saved entry dict, or None if it was a duplicate.
        """
        embedding = self._embed(fact)

        # Dedup against existing knowledge
        existing = self._load_knowledge_embeddings()
        should_write, dup_id = self._deduplicator.should_write(
            fact, embedding, existing,
        )
        if not should_write:
            return None

        now = datetime.now(timezone.utc)
        knowledge_id = str(uuid.uuid4())

        entry = {
            'id': knowledge_id,
            'fact': fact,
            'category': category,
            'source_memories': source_memories or [],
            'created_at': now.isoformat(),
            'confidence': confidence,
            'embedding': embedding,
        }

        self._atomic_write(
            os.path.join(KNOWLEDGE_DIR, f'{knowledge_id}.json'),
            entry,
        )

        return entry

    def get_knowledge(self, knowledge_id: str) -> dict | None:
        """Load a single knowledge entry by ID."""
        fpath = os.path.join(KNOWLEDGE_DIR, f'{knowledge_id}.json')
        if not os.path.exists(fpath):
            return None
        try:
            with open(fpath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def list_knowledge(self, category: str | None = None) -> list[dict]:
        """List all knowledge entries, optionally filtered by category."""
        entries = []
        if not os.path.isdir(KNOWLEDGE_DIR):
            return entries

        for fname in os.listdir(KNOWLEDGE_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(KNOWLEDGE_DIR, fname)
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            if category and data.get('category') != category:
                continue

            entries.append(data)

        return entries

    # ─── Internal Helpers ───────────────────────────────────────────

    def _atomic_write(self, filepath: str, data: dict) -> None:
        """Write JSON atomically: tmpfile in same dir, then os.replace."""
        dirpath = os.path.dirname(filepath)
        fd, tmppath = tempfile.mkstemp(dir=dirpath, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmppath, filepath)
        except BaseException:
            # Clean up tmpfile on failure
            try:
                os.unlink(tmppath)
            except OSError:
                pass
            raise

    def _load_memory_embeddings(self) -> list[tuple[str, list[float]]]:
        """Load (memory_id, embedding) pairs from all non-archived memories."""
        result = []
        if not os.path.isdir(MEMORIES_DIR):
            return result

        for fname in os.listdir(MEMORIES_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(MEMORIES_DIR, fname)
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
                if data.get('archived', False):
                    continue
                emb = data.get('embedding')
                if emb:
                    result.append((data['id'], emb))
            except (json.JSONDecodeError, OSError, KeyError):
                continue

        return result

    def _load_knowledge_embeddings(self) -> list[tuple[str, list[float]]]:
        """Load (knowledge_id, embedding) pairs from all knowledge entries."""
        result = []
        if not os.path.isdir(KNOWLEDGE_DIR):
            return result

        for fname in os.listdir(KNOWLEDGE_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(KNOWLEDGE_DIR, fname)
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
                emb = data.get('embedding')
                if emb:
                    result.append((data['id'], emb))
            except (json.JSONDecodeError, OSError, KeyError):
                continue

        return result

    def _check_supersession(self, new_memory: dict, new_embedding: list[float]) -> None:
        """Check if the new memory supersedes any existing memories.

        Superseded memories get correction_factor=0.3 -- preserved but deprioritized.
        """
        # Build MemoryRecord for the new memory
        new_record = self._to_record(new_memory)

        # Load existing memories with embeddings
        existing = []
        for mem_data in self.list_memories():
            emb = mem_data.get('embedding')
            if emb:
                record = self._to_record(mem_data)
                existing.append((record, emb))

        if not existing:
            return

        superseded_ids = self._supersession.detect(new_record, new_embedding, existing)

        for mem_id in superseded_ids:
            mem = self.get_memory(mem_id)
            if mem and mem.get('correction_factor', 1.0) > 0.3:
                mem['correction_factor'] = 0.3
                # Recalculate decay score with new correction factor
                record = self._to_record(mem)
                mem['decay_score'] = self._scorer.calculate(record)
                self._atomic_write(
                    os.path.join(MEMORIES_DIR, f'{mem_id}.json'),
                    mem,
                )

    def _to_record(self, data: dict) -> MemoryRecord:
        """Convert a memory dict to a MemoryRecord for scoring."""
        created_at = data.get('created_at', '')
        if isinstance(created_at, str) and created_at:
            try:
                created_dt = datetime.fromisoformat(created_at)
            except ValueError:
                created_dt = datetime.now(timezone.utc)
        else:
            created_dt = datetime.now(timezone.utc)

        last_accessed = data.get('last_accessed')
        if isinstance(last_accessed, str) and last_accessed:
            try:
                last_accessed_dt = datetime.fromisoformat(last_accessed)
            except ValueError:
                last_accessed_dt = None
        else:
            last_accessed_dt = None

        return MemoryRecord(
            memory_id=data.get('id', ''),
            content=data.get('content', ''),
            collection=data.get('collection', 'episodic'),
            created_at=created_dt,
            access_count=data.get('access_count', 0),
            last_accessed=last_accessed_dt,
            correction_factor=data.get('correction_factor', 1.0),
            decay_score=data.get('decay_score', 1.0),
            archived=data.get('archived', False),
        )

"""
Three-mode retriever for Daimonion.

Provides three retrieval strategies driven by the classifier's query type:

  1. current_status  -- entity-filtered, recency-sorted, top 5
  2. general_knowledge -- hybrid search with diversity, balanced weights, top 5
  3. memory_recall -- broad semantic search, decay suppressed, expanded to top 7

Two backends:
  - Graphiti/Kuzu (if graphiti_core is installed): full graph-based retrieval
  - Local fallback: searches memories/knowledge JSON files using local embeddings

Each mode returns a context dict with memory_candidates and knowledge_candidates
formatted with full metadata for LLM relevance judgment.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from src.config import KNOWLEDGE_DIR, MEMORIES_DIR

# Try Graphiti -- gracefully degrade to local search if unavailable
try:
    from graphiti_core import Graphiti
    from graphiti_core.search.search_config import (
        EdgeReranker,
        EdgeSearchConfig,
        EdgeSearchMethod,
        EpisodeSearchConfig,
        EpisodeSearchMethod,
        NodeReranker,
        NodeSearchConfig,
        NodeSearchMethod,
        SearchConfig,
    )
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False


def _is_ambiguous(candidates: list[dict], threshold: float = 0.15) -> bool:
    """Check if top results are too close in score to distinguish."""
    scores = [c.get('score') for c in candidates[:5] if c.get('score') is not None]
    if len(scores) < 2:
        return False
    return (max(scores) - min(scores)) < threshold


# ─── Local Fallback Retriever ───────────────────────────────────────────

class LocalRetriever:
    """Fallback retriever that searches JSON files directly with local embeddings.

    Used when Graphiti is not installed. Loads memory/knowledge JSON files
    and ranks by cosine similarity using local sentence-transformers embeddings.
    """

    def __init__(self):
        # Lazy import to avoid loading model at module level
        self._embed_fn = None

    def _get_embed(self):
        if self._embed_fn is None:
            from src.memory.embeddings import embed
            self._embed_fn = embed
        return self._embed_fn

    def _load_memories(self) -> list[dict]:
        """Load all non-archived memory JSON files."""
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
                if not data.get('archived', False):
                    memories.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return memories

    def _load_knowledge(self) -> list[dict]:
        """Load all knowledge JSON files."""
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
                entries.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return entries

    def _score_candidates(
        self, query_embedding: list[float], items: list[dict], text_key: str
    ) -> list[tuple[dict, float]]:
        """Score items by cosine similarity to query embedding."""
        from src.memory.deduplication import cosine_similarity

        scored = []
        for item in items:
            item_emb = item.get('embedding')
            if item_emb:
                sim = cosine_similarity(query_embedding, item_emb)
                scored.append((item, sim))
            else:
                # No embedding stored -- compute on the fly
                text = item.get(text_key, '')
                if text:
                    embed = self._get_embed()
                    item_emb = embed(text)
                    sim = cosine_similarity(query_embedding, item_emb)
                    scored.append((item, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _format_memory(self, mem: dict, score: float) -> dict:
        return {
            'uuid': mem.get('id', ''),
            'fact': mem.get('content', ''),
            'name': mem.get('collection', 'episodic'),
            'created_at': mem.get('created_at'),
            'valid_at': mem.get('source_date'),
            'score': score,
            'source_type': 'memory',
            'decay_score': mem.get('decay_score', 1.0),
            'collection': mem.get('collection', 'episodic'),
        }

    def _format_knowledge(self, entry: dict, score: float) -> dict:
        return {
            'uuid': entry.get('id', ''),
            'fact': entry.get('fact', ''),
            'name': entry.get('category', ''),
            'created_at': entry.get('created_at'),
            'confidence': entry.get('confidence', 1.0),
            'score': score,
            'source_type': 'knowledge',
        }

    async def retrieve(self, query: str, config: dict) -> dict:
        """Retrieve context using local JSON search.

        Mimics the three-mode interface but backed by file-based search.
        """
        mode = config.get('retrieval_mode', 'general_knowledge')
        top_k = config.get('top_k', 5 if mode != 'memory_recall' else 7)

        embed = self._get_embed()
        query_embedding = embed(query)

        # Score memories
        memories = self._load_memories()
        scored_memories = self._score_candidates(query_embedding, memories, 'content')

        # For current_status, filter out expired/old and sort by recency
        if mode == 'current_status':
            # Sort by date (most recent first), then by score
            scored_memories.sort(
                key=lambda x: x[0].get('source_date') or x[0].get('created_at') or '',
                reverse=True,
            )

        memory_candidates = [
            self._format_memory(mem, score)
            for mem, score in scored_memories[:top_k]
        ]

        # Score knowledge
        knowledge_items = self._load_knowledge()
        scored_knowledge = self._score_candidates(query_embedding, knowledge_items, 'fact')
        knowledge_candidates = [
            self._format_knowledge(entry, score)
            for entry, score in scored_knowledge[:3]
        ]

        result: dict[str, Any] = {
            'memory_candidates': memory_candidates,
            'knowledge_candidates': knowledge_candidates,
            'retrieval_mode': mode,
        }

        # For memory_recall, check ambiguity
        if mode == 'memory_recall' and _is_ambiguous(memory_candidates):
            result['present_candidates'] = True
            result['clarification_prompt'] = (
                'I found a few things that might match. Which one were you thinking of?'
            )

        return result


# ─── Graphiti Retriever ─────────────────────────────────────────────────

class GraphitiRetriever:
    """Full retriever using Graphiti's search API.

    Only instantiated when graphiti_core is available.
    """

    def __init__(self, graphiti: Any, group_id: str = 'daimonion'):
        self.graphiti = graphiti
        self.group_id = group_id

    async def retrieve(self, query: str, config: dict) -> dict:
        """Retrieve context using the mode specified by the classifier."""
        mode = config.get('retrieval_mode', 'general_knowledge')

        if mode == 'current_status':
            return await self._status_retrieval(query, config)
        elif mode == 'memory_recall':
            return await self._recall_retrieval(query, config)
        else:
            return await self._knowledge_retrieval(query, config)

    async def _fallback_search(self, query: str, top_k: int) -> list[dict]:
        """Fallback to Graphiti's basic search() when search_() returns empty."""
        edges = await self.graphiti.search(
            query=query,
            num_results=top_k,
            group_ids=[self.group_id],
        )
        return [self._format_edge(edge, score=None) for edge in edges]

    async def _status_retrieval(self, query: str, config: dict) -> dict:
        """Entity-timeline retrieval for status queries."""
        top_k = config.get('top_k', 5)
        search_config = self._build_status_config(top_k)

        results = await self.graphiti.search_(
            query=query,
            config=search_config,
            group_ids=[self.group_id],
        )

        candidates = []
        for i, edge in enumerate(results.edges):
            score = results.edge_reranker_scores[i] if i < len(results.edge_reranker_scores) else None
            if edge.expired_at is not None:
                continue
            candidates.append(self._format_edge(edge, score))

        candidates.sort(
            key=lambda c: c.get('valid_at') or c.get('created_at') or '',
            reverse=True,
        )

        episode_candidates = []
        for i, ep in enumerate(results.episodes):
            score = results.episode_reranker_scores[i] if i < len(results.episode_reranker_scores) else None
            episode_candidates.append(self._format_episode(ep, score))

        return {
            'memory_candidates': candidates[:top_k],
            'knowledge_candidates': episode_candidates[:3],
            'retrieval_mode': 'current_status',
        }

    async def _knowledge_retrieval(self, query: str, config: dict) -> dict:
        """Standard hybrid retrieval with balanced scoring."""
        top_k = config.get('top_k', 5)
        search_config = self._build_knowledge_config(top_k)

        results = await self.graphiti.search_(
            query=query,
            config=search_config,
            group_ids=[self.group_id],
        )

        candidates = []
        for i, edge in enumerate(results.edges):
            score = results.edge_reranker_scores[i] if i < len(results.edge_reranker_scores) else None
            candidates.append(self._format_edge(edge, score))

        if not candidates:
            candidates = await self._fallback_search(query, top_k)

        episode_candidates = []
        for i, ep in enumerate(results.episodes):
            score = results.episode_reranker_scores[i] if i < len(results.episode_reranker_scores) else None
            episode_candidates.append(self._format_episode(ep, score))

        return {
            'memory_candidates': candidates[:top_k],
            'knowledge_candidates': episode_candidates[:3],
            'retrieval_mode': 'general_knowledge',
        }

    async def _recall_retrieval(self, query: str, config: dict) -> dict:
        """Broad semantic search for vague recall queries."""
        top_k = config.get('top_k', 7)
        search_config = self._build_recall_config(top_k)

        results = await self.graphiti.search_(
            query=query,
            config=search_config,
            group_ids=[self.group_id],
        )

        candidates = []
        for i, edge in enumerate(results.edges):
            score = results.edge_reranker_scores[i] if i < len(results.edge_reranker_scores) else None
            candidates.append(self._format_edge(edge, score))

        if not candidates:
            candidates = await self._fallback_search(query, top_k)

        episode_candidates = []
        for i, ep in enumerate(results.episodes):
            score = results.episode_reranker_scores[i] if i < len(results.episode_reranker_scores) else None
            episode_candidates.append(self._format_episode(ep, score))

        result: dict[str, Any] = {
            'memory_candidates': candidates[:top_k],
            'knowledge_candidates': episode_candidates[:3],
            'retrieval_mode': 'memory_recall',
        }

        if _is_ambiguous(candidates):
            result['present_candidates'] = True
            result['clarification_prompt'] = (
                'I found a few things that might match. Which one were you thinking of?'
            )

        return result

    @staticmethod
    def _format_edge(edge: Any, score: float | None = None) -> dict:
        return {
            'uuid': edge.uuid,
            'fact': edge.fact,
            'name': edge.name,
            'created_at': edge.created_at.isoformat() if edge.created_at else None,
            'valid_at': edge.valid_at.isoformat() if edge.valid_at else None,
            'invalid_at': edge.invalid_at.isoformat() if edge.invalid_at else None,
            'expired_at': edge.expired_at.isoformat() if edge.expired_at else None,
            'episodes': edge.episodes,
            'score': score,
            'source_type': 'edge',
        }

    @staticmethod
    def _format_episode(episode: Any, score: float | None = None) -> dict:
        return {
            'uuid': episode.uuid,
            'fact': episode.content,
            'name': episode.name,
            'created_at': episode.created_at.isoformat() if episode.created_at else None,
            'valid_at': episode.valid_at.isoformat() if episode.valid_at else None,
            'source_description': episode.source_description,
            'score': score,
            'source_type': 'episode',
        }

    @staticmethod
    def _build_status_config(top_k: int = 5) -> Any:
        return SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.bm25, EdgeSearchMethod.cosine_similarity],
                reranker=EdgeReranker.episode_mentions,
                sim_min_score=0.0,
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.bm25, NodeSearchMethod.cosine_similarity],
                reranker=NodeReranker.rrf,
            ),
            episode_config=EpisodeSearchConfig(
                search_methods=[EpisodeSearchMethod.bm25],
            ),
            limit=top_k,
        )

    @staticmethod
    def _build_knowledge_config(top_k: int = 5) -> Any:
        return SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[
                    EdgeSearchMethod.cosine_similarity,
                    EdgeSearchMethod.bm25,
                ],
                reranker=EdgeReranker.rrf,
                sim_min_score=0.0,
            ),
            node_config=NodeSearchConfig(
                search_methods=[
                    NodeSearchMethod.cosine_similarity,
                    NodeSearchMethod.bm25,
                ],
                reranker=NodeReranker.rrf,
            ),
            limit=top_k,
        )

    @staticmethod
    def _build_recall_config(top_k: int = 7) -> Any:
        return SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[
                    EdgeSearchMethod.cosine_similarity,
                    EdgeSearchMethod.bm25,
                ],
                reranker=EdgeReranker.rrf,
                sim_min_score=0.0,
            ),
            node_config=NodeSearchConfig(
                search_methods=[
                    NodeSearchMethod.cosine_similarity,
                    NodeSearchMethod.bm25,
                ],
                reranker=NodeReranker.rrf,
            ),
            limit=top_k,
        )


# ─── Factory ────────────────────────────────────────────────────────────

def create_retriever(graphiti_instance: Any | None = None, group_id: str = 'daimonion'):
    """Create the appropriate retriever based on available dependencies.

    If graphiti_instance is provided and graphiti_core is installed,
    returns a GraphitiRetriever. Otherwise returns a LocalRetriever
    that searches JSON files with local embeddings.
    """
    if GRAPHITI_AVAILABLE and graphiti_instance is not None:
        return GraphitiRetriever(graphiti_instance, group_id)
    return LocalRetriever()

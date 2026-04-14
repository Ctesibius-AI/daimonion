"""
Local Embedder for Graphiti — bridges sentence-transformers to Graphiti's EmbedderClient interface.

Uses the same all-MiniLM-L6-v2 model as the rest of Daimonion's embedding system.
384-dim vectors, zero API cost, runs on-device.
"""

from __future__ import annotations

import logging
from typing import Iterable

from graphiti_core.embedder import EmbedderClient

logger = logging.getLogger('daimonion.local_embedder')

_model = None


def _get_model():
    """Lazy-load sentence-transformers model (singleton)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info('Local embedder loaded: all-MiniLM-L6-v2 (384-dim)')
    return _model


class LocalEmbedder(EmbedderClient):
    """Graphiti-compatible embedder using local sentence-transformers.

    Implements the EmbedderClient interface so Graphiti can use local
    embeddings instead of OpenAI.
    """

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        """Embed a single string. Returns 384-dim float vector."""
        model = _get_model()
        if isinstance(input_data, str):
            embedding = model.encode(input_data)
        elif isinstance(input_data, list) and input_data and isinstance(input_data[0], str):
            # List of strings — embed the first one
            embedding = model.encode(input_data[0])
        else:
            # Passthrough for pre-computed embeddings
            return list(input_data)
        return embedding.tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """Embed a batch of strings. Returns list of 384-dim float vectors."""
        model = _get_model()
        embeddings = model.encode(input_data_list)
        return [e.tolist() for e in embeddings]

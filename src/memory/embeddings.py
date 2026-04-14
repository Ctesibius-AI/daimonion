"""
Local embeddings module for Daimonion.

Uses sentence-transformers (all-MiniLM-L6-v2) for 384-dimensional embeddings.
Lazy initialization -- the model is not loaded until first use.
Thread-safe singleton -- safe for concurrent access.

NO OpenAI dependency. All embeddings computed locally.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_NAME = 'all-MiniLM-L6-v2'
EMBEDDING_DIM = 384

_lock = threading.Lock()
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Get or lazily initialize the sentence-transformers model.

    Thread-safe: uses double-checked locking so only the first caller
    pays the initialization cost.
    """
    global _model
    if _model is not None:
        return _model

    with _lock:
        # Double-check after acquiring lock
        if _model is not None:
            return _model

        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        return _model


def embed(text: str) -> list[float]:
    """Embed a single text string into a 384-dim vector.

    Args:
        text: The text to embed.

    Returns:
        A list of 384 floats representing the embedding.
    """
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings into 384-dim vectors.

    More efficient than calling embed() in a loop because
    sentence-transformers can batch internally.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embeddings, one per input text.
    """
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]

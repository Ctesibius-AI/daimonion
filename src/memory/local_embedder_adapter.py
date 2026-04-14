"""
local_embedder_adapter.py — Local adapters for Graphiti.

Implements Graphiti's EmbedderClient and CrossEncoderClient interfaces
using local sentence-transformers. No OpenAI API needed. Zero cost.
"""

from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.cross_encoder.client import CrossEncoderClient

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


class LocalSentenceTransformerEmbedder(EmbedderClient):
    """Local embedder using sentence-transformers. 384-dim, all-MiniLM-L6-v2."""

    async def create(self, input_data) -> list[float]:
        model = _get_model()
        if isinstance(input_data, str):
            return model.encode(input_data).tolist()
        if isinstance(input_data, list) and input_data and isinstance(input_data[0], str):
            # Return embedding for first string (Graphiti calls create() with single input)
            return model.encode(input_data[0]).tolist()
        return model.encode(str(input_data)).tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        model = _get_model()
        embeddings = model.encode(input_data_list)
        return [emb.tolist() for emb in embeddings]


class LocalCrossEncoder(CrossEncoderClient):
    """Local cross-encoder using sentence-transformers cosine similarity.

    Not a true cross-encoder (no joint encoding), but provides basic
    reranking using embedding similarity. Good enough for local use.
    """

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        model = _get_model()
        query_emb = model.encode(query)
        passage_embs = model.encode(passages)

        import numpy as np
        scores = np.dot(passage_embs, query_emb) / (
            np.linalg.norm(passage_embs, axis=1) * np.linalg.norm(query_emb)
        )

        ranked = sorted(
            zip(passages, scores.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked

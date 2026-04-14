"""
Daimonion memory system.

Modules:
  decay          - Decay scoring (time x access x correction)
  deduplication  - Write-time dedup and supersession detection
  embeddings     - Local sentence-transformers embeddings (384-dim)
  retrieval      - Three-mode retriever (Graphiti or local fallback)
  store          - Persistent JSON storage with atomic writes
"""

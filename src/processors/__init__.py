"""
Synapsis (Σύναψις) — Daimonion's connection-forming processor.

The brain's night work: consolidate memories, form connections, prune decay,
integrate new knowledge into the graph. Runs nightly or on-demand ("save").

Architecture: SynapsisOrchestrator coordinates extraction, dedup, analysis,
research, and compilation across the Loci memory system.

Intelligence chain (sequential, Sonnet):
  EXTRACTOR — four-lens extraction from daily logs
  DEDUPLICATOR — compare against existing, supersession
  ANALYZER — philosophical lens + drift detection
  RESEARCHER — web search on flagged topics

Information agents (parallel, Haiku/API):
  SPORTS, NEWS, WEATHER

Final:
  COMPILER — writes to Loci (MemPalace/ChromaDB, Kuzu/Graph, Vault/Wiki)
"""

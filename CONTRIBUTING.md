# Contributing to Daimonion

**Last updated:** 2026-04-14

## Code Style

- Python 3.12+ with type hints
- No OpenAI dependencies. Embeddings are local (sentence-transformers).
- All file paths come from `src/config.py`. Never hardcode paths.
- Atomic writes everywhere: write to `.tmp`, then `os.replace`.
- Never delete data. Only archive.

## Testing

```bash
# Run all tests
python -m pytest tests/ --tb=line

# Run specific test file
python -m pytest tests/test_decay.py -v

# Run with coverage (if installed)
python -m pytest tests/ --cov=src --cov-report=term-missing
```

All PRs must pass existing tests (148 currently). New features need tests.

## Project Rules

1. **Philosophy is bedrock.** Philosophical entries never decay. The epistemic anchor never changes. Don't modify `skills/philosophy/traits/` without discussion.
2. **No data deletion.** Only archive. `correction_factor = 0.3` for superseded, `archived = true` for decayed.
3. **No OpenAI dependency.** Embeddings are local via sentence-transformers. The `LocalEmbedder` bridges to Graphiti.
4. **Three storage layers.** ChromaDB (MemPalace) for verbatim + memories. Graphiti (Kuzu) for entities + relations. Vault (Markdown) for human reading. Don't add a fourth.
5. **Identity and Operations are separate.** `skills/identity/soul.md` (Opus full) = who. `skills/identity/soul_core.md` (Sonnet lean) = who, compressed. Skills = what. Traits = how. Philosophy = why.
6. **Every API call tracked.** Use `tracker.log()` for Anthropic, `tracker.log_brave()` for Brave.
7. **Heavy dependencies are optional.** Wrap in try/except: graphiti_core, kuzu, kokoro, whisper, torch. System degrades gracefully.
8. **Model allocation follows purpose.** Sonnet for extraction and analysis. Haiku for diary summaries, briefing compilation, information agents, and Graphiti writes alongside Sonnet extraction. Never use Haiku for core extraction or analysis.
9. **Adaptive traits evolve.** Behavioral traits are living documents. The Synapsis rewrites them when drift is confirmed 3+ nights. Old versions archived to `skills/traits/_archive/`.
10. **The epistemic anchor is the most important instruction.** The chain is: phantasia (receive) then exetasis (examine) then noesis (understand). Propeteia — agreeing without investigating — is the named failure. Don't weaken this.

## Architecture

See [docs/DAIMONION-PROJECT-DOCUMENTATION.md](docs/DAIMONION-PROJECT-DOCUMENTATION.md) for the full system specification and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design.

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Night Orchestrator | `src/processors/synapsis_orchestrator.py` | 8-agent pipeline coordinator |
| Graphiti Writer | `src/memory/graphiti_writer.py` | Writes to Kuzu knowledge graph |
| Graphiti MCP Server | `src/mcp/graphiti_server.py` | 5 query tools for graph traversal (entity search, relations, multi-hop, recent, stats) |
| Memory Index Compiler | `src/processors/memory_index_compiler.py` | Builds MEMORY.md (9-day rolling index with multi-vertex refs) |
| Wiki Ingester | `src/processors/wiki_compiler.py` | Routes vault/raw/ documents to wiki subdirectories |
| Local Embedder | `src/memory/local_embedder.py` | Bridges sentence-transformers to Graphiti |
| Philosophy | `skills/philosophy/` | Permanent philosophical layer (anchor + traits + skills) |
| Pipeline | `src/core/pipeline.py` | Sonnet/Opus conversation engine |

## Graphiti MCP Server

The Graphiti MCP server at `src/mcp/graphiti_server.py` exposes the Kuzu knowledge graph to Pythia during conversation. It provides 5 tools:

- **entity search** — find entities by name or description
- **relations** — get relationships for a given entity
- **multi-hop** — traverse the graph across multiple edges
- **recent** — query recently added entities and relationships
- **stats** — graph statistics (entity count, relationship count, etc.)

The server is registered in Pythia's MCP configuration and runs alongside the conversation pipeline. It reads from the same Kuzu database that Synapsis writes to during nightly processing.

## Adding a New Synapsis Agent

1. Add the agent method to `SynapsisOrchestrator` class
2. Wire it into `_run_intelligence_chain()` or `_run_information_agents()`
3. Add output handling in `_run_compiler()`
4. Update the agent prompts at the bottom of the file
5. Write tests

## Running Synapsis

Entry point: `python scripts/run_synapsis.py [date] [--skip-extraction]`

## Adding a Philosophical Entry

1. Create in `skills/philosophy/skills/` using the enrichment format (WHY/HOW/FAILURE/CARE)
2. Only if structurally real — the principle must operate the same way as the Greek concept
3. Add trigger keywords to CLAUDE.md section 10
4. Update `skills/philosophy/README.md`

## Adding a Behavioral Trait

1. Create in `skills/traits/{thinking,communication,domains,context}/`
2. Keep under 200 tokens
3. Add trigger keywords to CLAUDE.md section 10
4. These are adaptive — Synapsis may rewrite them over time

## Adding a New Tool

1. Create the tool function in `src/tools/`
2. Add the tool definition to `TOOLS` list in `src/core/pipeline.py`
3. Add the handler in `PythiaPipeline._handle_tool()`
4. Write tests

## Pull Requests

- One logical change per PR
- Descriptive title (under 70 chars)
- Tests pass (148+)
- No new hardcoded paths
- No legacy system references in `src/`

## License

Apache 2.0. The extraction pipeline outputs (A1-A5) are intellectual property.

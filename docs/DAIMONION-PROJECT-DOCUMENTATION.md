# Daimonion — Project Documentation

**Version:** v5 (as of 2026-04-13)
**License:** Apache 2.0
**Language:** Python 3.12+
**Platform:** Tested on MacBook Air M1. Runs locally, no cloud services except Anthropic API and Brave Search API.

---

## 1. What Daimonion Is

Daimonion is an open-source system that adds persistent memory, identity, and a nightly processing pipeline to Claude Code. It turns a stateless LLM into a conversational partner that remembers across sessions, tracks how topics evolve over time, and maintains a searchable archive of everything discussed.

The system runs as a layer on top of Claude Code. It does not modify Claude Code itself. It uses Claude Code's native extension points (hooks, rules, skills, MCP servers, MEMORY.md) to add memory and behavioral consistency.

---

## 2. What Problem It Solves

Claude Code conversations are ephemeral. When a session ends, context is lost. The next session starts blank. For users who work with Claude Code daily on ongoing projects, this means:

- Re-explaining project context every session
- Losing track of decisions made in previous sessions
- No record of what was discussed or decided unless manually documented
- No way to ask "what did we decide about X last week?"

Daimonion addresses this by:

- Capturing every exchange in real-time to a local vector database (MemPalace/ChromaDB)
- Running a nightly pipeline (Synapsis) that extracts memories, facts, entities, and relationships from daily conversations
- Storing verified relationships in a temporal knowledge graph (Graphiti/Kuzu)
- Compiling a 9-day rolling index (MEMORY.md) that Claude Code loads automatically at session start
- Maintaining a human-browsable wiki (Obsidian-compatible markdown) with run reports, research compilations, and project pages

---

## 3. Architecture Overview

### 3.1 Four Named Components

| Component | Role |
|-----------|------|
| **Daimonion** | The system as a whole |
| **Pythia** | The conversation interface — Claude Code with identity, rules, and skills loaded |
| **Loci** | The memory layer — three storage systems connected by Synapsis |
| **Synapsis** | The connector — nightly pipeline that extracts, verifies, and writes to all storage layers |

### 3.2 Three Storage Systems

| System | Technology | What It Stores | When It's Written | How It's Searched |
|--------|-----------|----------------|-------------------|-------------------|
| **MemPalace** | ChromaDB + SQLite KG | Verbatim conversation text + quick-lookup facts | Real-time (Stop hook during conversation) | 19 MCP tools (semantic search, KG query, diary read/write) |
| **Graphiti** | Kuzu embedded graph DB | Entities, relationships, temporal connections | Batch (Synapsis pipeline, Haiku entity extraction) | Graphiti MCP server (7 tools: entity search, relations, multi-hop, recent, stats, fact_add, fact_query) |
| **Wiki/Karpathy** | Obsidian-compatible markdown | Run reports, research compilations, project pages | Batch (wiki_ingester routes documents from vault/raw/) | File read, Obsidian browse |

All data is stored locally at `~/.daimonion/`. No cloud storage.

### 3.3 Memory Tiers

| Tier | Scope | Mechanism | Latency |
|------|-------|-----------|---------|
| **Active** | Current conversation | Claude Code context window | Instant |
| **Short-term** | Last 9 days | MEMORY.md (compiled index, auto-loaded) + Diary | Instant at session start |
| **Long-term** | Everything | MemPalace (semantic search) + Graphiti (graph traversal) | On-demand search |

The Wiki is not a tier — it's a reference library available across all tiers.

---

## 4. How It Works

### 4.1 During a Conversation

- A **Stop hook** fires after each Claude Code response, capturing the exchange to MemPalace as a verbatim "drawer" in ChromaDB.
- A **response validator** hook checks for behavioral violations (προπέτεια/rash assent, verbosity, comfort theater, filler, over-apologizing).
- The user can explicitly save facts with `kg_add` (writes to MemPalace's knowledge graph).
- The user can write diary entries with `mempalace_diary_write` for milestones or session checkpoints.

### 4.2 On "Save" (Lightweight Checkpoint)

- Writes one diary entry to MemPalace with: what was worked on, decisions made, NEXT_ACTION, CONTEXT.
- No pipeline runs. Instant.

### 4.3 On "Good Night" (Full Processing)

- Writes the diary entry (same as Save).
- Triggers the full Synapsis pipeline.

### 4.4 Nightly (Cron at 3 AM)

- The same Synapsis pipeline runs automatically via cron.
- Catches any day where the user forgot to say "Good Night."

### 4.5 On Session Start

1. `date` — check current time.
2. `mempalace_diary_read` — load last 5 diary entries (what happened, what's next).
3. MEMORY.md — auto-loaded by Claude Code (9-day rolling index with pointers into all three storage systems).
4. Rules — auto-loaded by Claude Code (9 behavioral/philosophical rules).
5. Skills — loaded on-demand when conversation triggers match.

---

## 5. The Synapsis Pipeline

Synapsis is the only custom orchestration code. Everything else is stock (MemPalace, Graphiti, Claude Code native features).

**Entry point:** `python scripts/run_synapsis.py [date] [--skip-extraction]`

### Pipeline Steps

| Step | Agent | Model | What It Does |
|------|-------|-------|-------------|
| 0 | — | Python | Extract daily logs from Claude Code JSONL session files |
| 1 | Extractor | Sonnet | Four-lens extraction: behavior, relationship, design, philosophy |
| 2 | Deduplicator | Sonnet | Compare new extractions against existing memories, detect supersession |
| 3 | Analyzer | Sonnet | Pattern detection, drift analysis, research flagging |
| 4 | Researcher | Sonnet + Brave | Web search on flagged topics, compile reports |
| 5 | Compiler | Python + Haiku | Write to ChromaDB, Graphiti/Kuzu, MemPalace KG, compile briefing, build MEMORY.md |
| 6 | Sports | Haiku + Brave | Sports news filtered by user interests |
| 7 | News | Haiku + Brave | General news filtered by user interests |
| 8 | Weather | Python (no LLM) | Weather forecast via Open-Meteo API |
| — | QA Auditor | Python | 9 post-pipeline checks (research flow, session followups, trait sync, etc.) |
| — | Report | Python | Compile run report → vault/raw/ |
| — | Wiki Ingest | Python | Route vault/raw/ documents to wiki subdirectories |
| — | Diary | Python | Write stats + enriched summary with multi-vertex refs |

Agents 1-4 run sequentially (each depends on previous output). Agents 6-8 run in parallel with the intelligence chain. Agent 5 runs after both tracks complete.

### Pipeline Output Per Day

| Output | Location | Count (typical) |
|--------|----------|-----------------|
| Memories | `~/.daimonion/memories/*.json` | 10-25 |
| Knowledge | `~/.daimonion/knowledge/*.json` | 5-15 |
| KG triples | MemPalace ChromaDB | 5-30 |
| Graphiti entities | Kuzu | 10-40 |
| Graphiti relationships | Kuzu | 10-50 |
| Diary stats entry | MemPalace ChromaDB | 1 |
| Diary summary entry | MemPalace ChromaDB | 1 (with multi-vertex refs) |
| Daily briefing | `~/.daimonion/vault/daily-briefings/` | 1 |
| Run report | `~/.daimonion/vault/synapsis-runs/` | 1 |
| Research reports | `~/.daimonion/vault/research/` | 0-3 |
| MEMORY.md | `~/.claude/projects/.../memory/MEMORY.md` | 1 (9-day rolling, up to 200 lines) |

### Cost Per Run

Approximately $0.10-0.15 per day on Anthropic API (Sonnet for intelligence chain, Haiku for information agents and briefing compilation). Brave Search API free tier allows ~2,000 queries/month.

---

## 6. MEMORY.md — The Session Bridge

MEMORY.md is the mechanism that gives Claude Code context across sessions. It is:

- Written by Synapsis at the end of each pipeline run
- Placed at the native Claude Code memory path (`~/.claude/projects/<project>/memory/MEMORY.md`)
- Auto-loaded by Claude Code at session start (no manual loading required)
- Capped at 200 lines, 9-day rolling window

### Format (AAAK Multi-Vertex Index)

Each line is a compressed entry with pointers into all three storage systems:

```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing→revised|gr:entity_c3d4|wiki:decisions/pricing-model|★★★
```

**Sparse ref convention:**
- `TBD` — Synapsis hasn't processed this yet (entry exists but refs pending)
- `N/A` — Synapsis evaluated and determined no ref is needed in that system

---

## 7. Identity and Behavioral System

Daimonion includes an identity layer that shapes how Pythia responds. This is implemented entirely through Claude Code's native extension points.

### 7.1 Rules (9 files, always loaded)

| Rule | Purpose |
|------|---------|
| behavioral-anchor.md | Epistemic anchor: φαντασία → ἐξέτασις → νόησις. Named failure: προπέτεια (rash assent) |
| parrhesia.md | Fearless truth-telling as care, not cruelty |
| elenchos.md | Bilateral examination — test claims from both directions |
| gnothi-seauton.md | Know what you know and what you don't — no confident guessing |
| meden-agan.md | Nothing in excess — stop when the point is made |
| memory-routing.md | Retrieval protocol across all storage systems |
| capture-rules.md | What to capture, diary protocol, never-delete policy |
| time-awareness.md | Check date before time-dependent statements |
| wiki-routing.md | Three memory layers, when to use each |

### 7.2 Skills (11 groups, loaded on demand)

Skills are triggered by conversation keywords. Each skill loads additional context and instructions.

| Skill | Triggers |
|-------|----------|
| Strategic Thinking | trade-offs, both sides, should I, decision |
| Analytical Mode | analyze, evaluate, compare, decompose |
| Building Mode | architecture, codebase, implement, refactor |
| Communication Tuning | verbose, correction, emotional, understated |
| Business Context | pricing, strategy, market, consultancy |
| Project Awareness | timeline, priority, milestone, what's next |
| Voice & Telegram | voice mode, telegram, progressive response |
| Research Mode | investigate, search, competitor, current events |
| Memory & Recall | remember, what did we, when did, check memory |
| Brainstorm Mode | what if, idea, explore, options |
| Synapsis | good night, save, run synapsis |

### 7.3 Identity Files

- `skills/identity/soul.md` — Full identity document (used with Opus)
- `skills/identity/soul_core.md` — Lean identity (used with Sonnet for lower token cost)

The identity was extracted from months of real conversations using a multi-stage extraction pipeline. The extraction skills are included in `skills/extraction/`.

---

## 8. Retrieval Protocol

When Pythia needs to recall information, she follows a layered search protocol. Most questions are answered at the first few layers. Deeper layers are for long-term recall and cross-referencing.

```
1. Context (current conversation)     → already in context window
2. MEMORY.md (9-day index)            → auto-loaded, instant
3. Diary (session summaries)          → mempalace_diary_read
4. MemPalace KG (quick facts)         → kg_query / kg_timeline
5. MemPalace search (verbatim)        → semantic search across drawers
6. Graphiti (deep connections)         → multi-hop traversal, temporal queries
7. Wiki (compiled knowledge)          → file read
```

---

## 9. Data Layout

All data resides at `~/.daimonion/`:

```
~/.daimonion/
├── memories/           Episodic memory records (JSON, one per memory)
├── knowledge/          Factual entries extracted from conversations (JSON)
├── mempalace/          ChromaDB database (verbatim drawers + KG + diary)
├── graph/              Kuzu embedded graph database (Graphiti)
├── daily_logs/         Daily conversation logs (markdown, extracted from JSONL)
├── vault/              Obsidian-compatible wiki
│   ├── projects/       Project summary pages
│   ├── decisions/      Decision records
│   ├── research/       Research compilation reports
│   ├── synapsis-runs/  Pipeline run reports
│   ├── daily-briefings/ Morning briefings
│   ├── concepts/       Concept pages
│   ├── entities/       Entity pages
│   └── raw/            Incoming documents (routed by wiki_ingester)
├── night_runs/         Synapsis step outputs and logs per date
├── qa/                 QA audit findings
├── archive/            Archived data (never deleted, only archived)
├── usage/              API usage logs
└── health/             Health check reports
```

---

## 10. Codebase Structure

```
daimonion/
├── src/
│   ├── config.py                    All paths, models, constants (92 lines)
│   ├── core/                        Conversation, pipeline, skill loader, chunker
│   ├── memory/                      Storage, decay, deduplication, embeddings, graph writer
│   ├── processors/                  Synapsis pipeline (orchestrator, extractor, analyzer, etc.)
│   ├── tools/                       Vault, web search, weather, RSS, usage tracking
│   ├── interfaces/                  Telegram bot, CLI
│   ├── voice/                       TTS/STT pipeline (Kokoro, Greek TTS)
│   ├── mcp/                         Graphiti MCP server
│   ├── validators/                  Response validator, verbatim capture
│   └── hooks/                       Real-time capture Stop hook
├── scripts/
│   ├── run_synapsis.py              Pipeline entry point
│   ├── extract_claude_sessions.py   JSONL → daily log conversion
│   └── pythia_tools.py              CLI wrappers
├── skills/                          131 markdown skill/trait/identity files
├── tests/                           148 tests across 8 test files
├── docs/                            Architecture, build plans, specs
└── archive/                         Previous pipeline iteration (preserved)
```

### Key File Sizes

| File | Lines | Role |
|------|-------|------|
| synapsis_orchestrator.py | ~1,470 | Pipeline orchestration (largest file) |
| qa_auditor.py | 669 | Post-pipeline QA checks |
| synapsis_extractor.py | 615 | Four-lens memory extraction |
| synapsis_compiler.py | 430 | Briefing compilation + storage writes |
| health_monitor.py | 419 | Subsystem health checks |
| memory/store.py | 403 | Memory storage with decay |
| wiki_compiler.py | 396 | Wiki page generation |
| direct_graph_writer.py | 349 | Direct Kuzu writes |
| memory_index_compiler.py | 263 | MEMORY.md builder |
| graphiti_server.py | 248 | MCP server for graph queries |

Total Python: ~26,000 lines across 67 source files.

---

## 11. Dependencies

### Required (pip)

| Package | Purpose |
|---------|---------|
| anthropic | Claude API access |
| graphiti-core | Temporal knowledge graph framework |
| kuzu | Embedded graph database (Graphiti backend) |
| sentence-transformers | Local embeddings (all-MiniLM-L6-v2, 384-dim) |
| mempalace | ChromaDB spatial memory with 19 MCP tools |
| python-telegram-bot | Telegram interface |
| httpx | HTTP client |
| python-dotenv | Environment variable loading |
| pyyaml | YAML parsing |
| feedparser | RSS feed parsing |
| mcp | Model Context Protocol SDK |

### External Services

| Service | Purpose | Required |
|---------|---------|----------|
| Anthropic API | LLM calls (Sonnet, Opus, Haiku) | Yes |
| Brave Search API | Web search for research step | Optional (pipeline continues without it) |
| Open-Meteo API | Weather forecasts | Optional (free, no key) |

### Not Used (by design)

- **OpenAI** — embeddings are local (sentence-transformers). Rule 1: never add OpenAI as a dependency.
- **Neo4j** — replaced by Kuzu (embedded, no server). Residual neo4j imports were removed.
- **Cloud storage** — all data local.

---

## 12. Current State (2026-04-14)

### Working

- Real-time capture (Stop hook → MemPalace, every exchange)
- MemPalace: 7,748 verbatim drawers, 227 extracted memories, KG read/write
- Graphiti: 789 entities, 1,409 relationships, 199 episodes in Kuzu (single write path via Haiku)
- Synapsis pipeline: single entry point, 8 agents + post-pipeline steps, runs end-to-end
- Diary: Haiku-generated daily summary (WORKED ON / DECIDED / COMPLETED / FLAGGED)
- MEMORY.md: 195 entries at native Claude Code path, auto-loaded
- Wiki: 100 pages across projects, research, run reports, briefings
- Graphiti MCP server: 7 tools registered in Pythia (entity_search, entity_relations, multi_hop, recent, stats, fact_add, fact_query)
- Response validator: check_propeteia (rash assent), verbosity, comfort theater, filler, over-apologizing
- QA auditor: 9 post-pipeline checks
- Action log + run reports → vault → wiki
- Cron: 3 AM daily
- Backfill: 12 days processed (March 30 – April 12)
- LongMemEval: 90.8% (500 questions, oracle dataset)
- 148 tests passing
- 9 rules, 11 skills loaded in Pythia

### Not Built

- The Clock (conversational tempo and gap detection)
- LongMemEval benchmark integration

### Not Validated

- Session restoration quality (does diary + MEMORY.md give enough context to start without re-reading old conversations?)
- Graphiti query usefulness (are multi-hop traversals producing meaningful answers?)
- QA auditor effectiveness (are the 9 checks catching real issues?)
- Long-term memory quality (does the system degrade over weeks/months?)

---

## 13. Where It Is Useful

### Strong Use Cases

- **Daily ongoing work with Claude Code** — projects that span weeks or months, where continuity across sessions matters.
- **Decision tracking** — "what did we decide about X and why?" is answerable via multi-dimensional search.
- **Research accumulation** — flagged topics are researched overnight, compiled into wiki pages.
- **Audit trail** — every pipeline run produces a report. Every report is archived. Nothing is deleted.

### Moderate Use Cases

- **Multi-project context switching** — MemPalace rooms organize conversations by topic, but cross-project queries depend on Graphiti quality.
- **Behavioral consistency** — rules enforce specific interaction patterns (epistemic anchor against rash assent, bilateral examination, truthful assessment). Useful for users who want an opinionated partner, not an agreeable assistant.

### Not Designed For

- **Multi-user systems** — single-user, single-machine design. No authentication, no access control.
- **Production deployment** — research/personal tool. No API rate limiting, no horizontal scaling.
- **General-purpose chatbot** — the identity and behavioral system is specific. A different user would need to re-extract their own identity.

---

## 14. How to Install and Run

### Prerequisites

- Python 3.12+
- Anthropic API key (Max subscription recommended for cost efficiency)
- Brave Search API key (optional, for research step)

### Setup

```bash
cd ~/daimonion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in API keys
cp .env.example .env
```

### Run

```bash
# Synapsis pipeline (manual)
python scripts/run_synapsis.py                    # process today
python scripts/run_synapsis.py 2026-04-08         # specific date
python scripts/run_synapsis.py --skip-extraction  # skip JSONL extraction

# CLI interface
python -m src.interfaces.cli

# Telegram bot
python -m src.interfaces.telegram_bot

# Tests
python -m pytest tests/ --tb=line

# Rebuild MEMORY.md
python -c "from src.processors.memory_index_compiler import compile_memory_index; print(compile_memory_index())"
```

### Cron (automatic nightly processing)

```
0 3 * * * /path/to/daimonion/.venv/bin/python scripts/run_synapsis.py >> /tmp/daimonion-synapsis.log 2>&1
```

---

## 15. Design Decisions

These are recorded decisions, not recommendations. Each reflects a specific trade-off made during development.

1. **Real-time capture via Stop hook.** Every exchange is written to MemPalace immediately. Trade-off: adds ~10 seconds latency per response for the hook.
2. **Three separate storage systems.** MemPalace for verbatim, Graphiti for relationships, Wiki for compiled knowledge. Trade-off: complexity for specialization.
3. **Graphiti receives memories via Haiku extraction.** Synapsis extracts with Sonnet (four-lens), then writes each memory to Graphiti via GraphitiWriter.write_episode. Haiku extracts entities and relationships per episode. Trade-off: richer entities at slightly higher cost (~$0.02/day for Haiku calls).
4. **Local embeddings only.** sentence-transformers (all-MiniLM-L6-v2) for all embeddings. No OpenAI dependency. Trade-off: lower quality than OpenAI embeddings, but no external dependency and no per-embedding cost.
5. **Never delete, only archive.** All data operations that remove data move it to `~/.daimonion/archive/`. Trade-off: disk usage grows, but no accidental data loss.
6. **Diary replaces session-start-briefing.** The diary in MemPalace is the authoritative session state. No separate briefing file. Trade-off: depends on MemPalace being available.
7. **MEMORY.md as compiled index.** A 9-day rolling index with pointers into all three storage systems. Written by Synapsis, loaded natively by Claude Code. Trade-off: stale until the next Synapsis run.
8. **"Save" is diary-only, "Good Night" triggers the full pipeline.** Trade-off: "Save" is instant but doesn't update MEMORY.md or Graphiti until the next full run.
9. **Sparse refs (TBD/N/A).** MEMORY.md entries can have missing refs. TBD = not yet processed. N/A = processed, no ref warranted. Trade-off: adds parsing complexity but distinguishes "pending" from "excluded."

---

## 16. Known Limitations

- **Synapsis is a single point of failure.** If the pipeline breaks, Graphiti, MEMORY.md, and the wiki stop updating. Real-time capture (MemPalace drawers) continues independently.
- **Session restoration is unvalidated.** The design claims diary + MEMORY.md provides enough context. This has not been stress-tested.
- **QA depth is structural, not semantic.** The QA auditor checks that data moved through the pipeline, not that the extracted content is accurate.
- **Graphiti query quality is partially validated.** 789 entities exist. LongMemEval scored 90.8% overall but multi-session (82.7%) shows room for improvement in cross-session entity resolution.
- **No alerting on cron failure.** If the 3 AM run fails, nothing notifies the user until they notice stale data.
- **MEMORY.md staleness.** Between a "Save" and the next Synapsis run, MEMORY.md does not reflect the most recent session. The diary fills this gap partially.
- **Complexity.** Six interconnected systems (ChromaDB, Kuzu, Obsidian markdown, Stop hooks, MCP servers, cron) create a maintenance surface. Each can fail independently.

---

## 17. Project History

- **March 30, 2026** — Day 1. Graphiti + Kuzu setup, neo4j removal, LocalEmbedder creation.
- **March 31 – April 8** — Memory system, night processor, extraction pipeline, Telegram bot, CLI, voice pipeline.
- **April 9** — Architecture review. BUILD-PLAN-v2.
- **April 10** — MemPalace integration. BUILD-PLAN-v4. Full rebuild of memory pipeline.
- **April 11** — Rules, skills, identity restructure. Claude Code native integration. BUILD-PLAN-v4 phases 1-5.
- **April 12** — Architecture v5. MEMORY.md design. Diary protocol. Three-system triangle.
- **April 13** — BUILD-PLAN-v5 execution. Pipeline consolidation, MEMORY.md compiler, Graphiti MCP server, wiki ingester, cron, full backfill (12 days reprocessed). KG write step and diary enrichment added.

Previous iterations are archived at `archive/old_pipeline/` (v1) and `~/.daimonion/archive/` (data snapshots).

---

*This document describes the system as built. It does not evaluate whether the design choices are optimal or whether the complexity is justified for the use case. Those assessments are recorded separately in the architecture review documents.*

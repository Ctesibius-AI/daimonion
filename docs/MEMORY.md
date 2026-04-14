# Memory System — Lifecycle Documentation

**Last updated:** 2026-04-14

## Overview

Daimonion uses three memory tiers and three storage vertices, with a reference library (Karpathy/Wiki) available across all tiers.

### Three Memory Tiers

| Tier | Scope | Mechanism | Latency |
|------|-------|-----------|---------|
| **Active** | Current conversation | Claude Code context window | Instant — already in context |
| **Short-term** | Last 9 days | MEMORY.md (AAAK compiled index) + Diary | Instant — loaded at session start |
| **Long-term** | Everything before | MemPalace (semantic + KG) + Graphiti (graph) | On demand — search when needed |

**Karpathy (Wiki)** is not a tier — it is the reference library. Reports, compiled knowledge, audit trail. Always available alongside all tiers.

Active memory is the context window. Claude Code handles it natively.
Short-term is the compiled index (MEMORY.md) plus diary entries. Both loaded at startup.
Long-term is MemPalace + Graphiti. Multi-dimensional search: semantic + KG facts + graph traversal.

### Three Storage Vertices (Loci)

| Vertex | Technology | What It Stores | When Written |
|--------|-----------|----------------|--------------|
| **MemPalace** | ChromaDB + SQLite KG | Verbatim conversation text + quick facts + diary | Real-time (Stop hook) |
| **Graphiti** | Kuzu embedded graph DB | Verified entities, relationships, episodes | Batch (Synapsis, post-QA) |
| **Wiki/Karpathy** | Obsidian-compatible markdown | Run reports, research compilations, project pages | Batch (wiki_ingester) |

All data stored locally at `~/.daimonion/`. No cloud storage.

---

## MEMORY.md — The Compiled Multi-Vertex Index

**Location:** `~/.claude/projects/-Users-pythia-gr-daimonion-pythia/memory/MEMORY.md`
**Written by:** Synapsis (memory_index_compiler.py)
**Loaded by:** Claude Code natively at session start (auto memory disabled; Synapsis is the sole writer)

### Properties

- **Rolling window:** 9 days
- **Line cap:** 200 lines maximum
- **Format:** AAAK (one line per entry, multi-vertex refs)
- **Rebuild frequency:** Every Synapsis run

### AAAK Line Format

Each line is a hyperedge connecting related items across all three storage vertices:

```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing→revised|gr:entity_c3d4|wiki:decisions/pricing-model|★★★
```

Fields, pipe-delimited:
1. **Date** — YYYY-MM-DD of the source conversation
2. **Topic** — dotted summary of the entry
3. **mp:** — MemPalace ref (drawer ID or memory ID)
4. **kg:** — MemPalace KG ref (triple summary)
5. **gr:** — Graphiti ref (entity or relationship UUID)
6. **wiki:** — Vault page path (relative to vault/)
7. **Stars** — Significance (★ to ★★★★★)

### Sparse Ref Convention

- `TBD` — Synapsis has not processed this entry yet; ref will be filled on the next run (e.g., `gr:TBD`)
- `N/A` — Synapsis evaluated the entry and determined no ref is warranted in that vertex (e.g., `gr:N/A`)

This distinguishes "not yet reached" from "reached and decided against."

### Examples

Pre-Synapsis (entry exists, refs pending):
```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing→revised|gr:TBD|wiki:TBD|★★★
```

Post-Synapsis (fact excluded from Graphiti):
```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing→revised|gr:N/A|wiki:decisions/pricing-model|★★★
```

---

## Diary System

The diary lives in MemPalace (ChromaDB, `mempalace_drawers` collection, room `diary`). It is the session state bridge between conversations.

### Two Entry Types Per Synapsis Run

**1. Stats entry** (machine-readable):
```
SYNAPSIS:2026-04-12|mem:14|kb:5|wiki:3|qa:2|dur:45230ms
```
- Metadata: `topic: synapsis_stats`, `agent: pythia`, `date: YYYY-MM-DD`

**2. Daily summary entry** (Haiku-generated, human-readable):
```
WORKED ON: Synapsis pipeline consolidation, MEMORY.md compiler, Graphiti MCP server.
DECIDED: Auto memory disabled — Synapsis is sole writer of MEMORY.md.
COMPLETED: Full backfill (Mar 30 – Apr 12), 148 tests passing.
FLAGGED: Multi-session retrieval gap (82.7% on LongMemEval).
---
refs: mp:mem_20260412_a1b2,mem_20260412_c3d4 | kb:5_promoted | gr:38_entities | wiki:synapsis-runs/synapsis-report-2026-04-12 | mem:14 | kb:5
```
- Metadata: `topic: daily_summary`, `agent: pythia`, `date: YYYY-MM-DD`
- Multi-vertex refs appended after `---` separator, pointing into all three vertices
- Structured: WORKED ON, DECIDED, COMPLETED, FLAGGED (empty sections skipped)

### Session Close Entries (User-Triggered)

Written via `mempalace_diary_write` on "Save" or "Good Night":
```
SESSION:2026-04-12|worked.on:pipeline,MEMORY.md,benchmarks
refs:kg_entries.and.drawer_ids.from.this.session
rooms.touched:architecture,decisions
NEXT_ACTION:exact.next.step
BLOCKED:if.any
CONTEXT:what.Chatzi.was.doing.when.he.left
```

NEXT_ACTION must be specific enough to resume without digging. CONTEXT enables context-aware re-engagement.

### Diary as Session Briefing

At session start, Pythia reads the last 5 diary entries via `mempalace_diary_read`. The diary IS the briefing — no separate session-start-briefing file.

---

## Retrieval Protocol (7 Steps)

Order matters. Work down the layers. Most questions answered at steps 1-3.

```
Question asked
    │
    ├── 1. Context (Active tier)
    │   └── Answer in current conversation? → done
    │
    ├── 2. MEMORY.md (Short-term, 9-day AAAK index)
    │   └── Answer in compiled index? → done
    │   └── Follow ref pointer for detail? → done
    │
    ├── 3. Diary (Short-term, session summaries)
    │   └── Recent session notes via mempalace_diary_read? → done
    │
    ├── 4. MemPalace KG (Long-term, quick facts)
    │   └── Entity lookup: kg_query → done
    │   └── Timeline: kg_timeline → done
    │
    ├── 5. MemPalace search (Long-term, verbatim)
    │   └── Semantic search across drawers → done
    │
    ├── 6. Graphiti (Long-term, deep connections)
    │   └── Multi-hop traversal → done
    │   └── Temporal query → done
    │
    └── 7. Wiki / Karpathy (compiled knowledge)
        └── File read or Obsidian browse → done
```

Steps 4-7 are for long-term recall, deep connections, and compiled knowledge.

---

## Memory Lifecycle

### Creation

**During conversation (real-time):**
- Stop hook fires after each Claude Code response → `mempalace_add_drawer` (verbatim chunk to ChromaDB)
- User says "remember this" → `mempalace_kg_add` (fact to MemPalace KG)
- Milestones → `mempalace_diary_write` (diary entry)
- No extraction in real-time; raw verbatim preserved as-is

**During Synapsis (batch):**
- Four-lens extraction (A1-A4): behavior, relationship, design, philosophy
- Writes to all three vertices: ChromaDB (extracted memories), Kuzu (entities/relations), Vault (wiki pages)
- Deduplication at write time (cosine similarity >= 0.82 → skip)
- Supersession detection (two-pass: embedding + LLM judge)

### Decay

```
decay_score = time_factor × access_factor × correction_factor
```

**time_factor:**
```
time_factor = rate ^ days_old
```

Decay rates by collection:

| Collection | Rate/Day | After 1 Year | Use For |
|-----------|---------|-------------|---------|
| `identity` | 0.999 | 0.69 | Personal traits, preferences, behavioral directives |
| `procedural` | 0.997 | 0.33 | Technical decisions, architecture choices |
| `insights` | 0.993 | 0.08 | Strategic observations, business conclusions |
| `episodic` | 0.985 | 0.004 | Specific events, conversations |
| `sessions` | 0.960 | ~0 (3 months) | Conversation summaries |

**access_factor:**
```
access_factor = min(1.0, 0.5 + min(access_count × 0.1, 0.3) + recency_boost)
```
- recency_boost: 0.2 if accessed within 7 days, 0.1 if within 30 days

**correction_factor:**

| State | Value |
|-------|-------|
| Current (default) | 1.0 |
| Superseded | 0.3 |
| Corrected | 0.1 |

### Supersession Detection (Two-Pass)

When information evolves ("pricing is 300" → "pricing is 200"):

1. **Pass 1 — Embedding:** Find existing memories with cosine similarity >= 0.82 AND older date
2. **Pass 2 — LLM (Sonnet):** Judge whether new memory REPLACES the old concept (prevents false positives)

Outcome:
- Old memory's `correction_factor` drops to 0.3 (preserved, deprioritized)
- Graphiti: old relationship gets `expired_at` set
- Old memory NEVER deleted — accessible for historical context

### Archive

- **Threshold:** `decay_score < 0.05` AND `age > 60 days`
- **Action:** `archived=true` in ChromaDB metadata
- **Policy:** NEVER deleted — accessible for historical queries, excluded from default retrieval

### The Rule

**Never delete. Only archive. History has value even when faded.**

---

## LongMemEval Benchmark

**Date:** 2026-04-14
**Benchmark:** LongMemEval (ICLR 2025), 500 questions, oracle dataset
**Stack:** MemPalace (ChromaDB drawers + KG search) → Claude Sonnet 4.6

### Result: 90.8% (454/500)

| Question Type | Score |
|---------------|-------|
| single-session-user | 98.6% (69/70) |
| single-session-preference | 96.7% (29/30) |
| temporal-reasoning | 93.2% (124/133) |
| knowledge-update | 91.0% (71/78) |
| single-session-assistant | 91.1% (51/56) |
| multi-session | 82.7% (110/133) |

### Leaderboard Context

| System | Score |
|--------|-------|
| MemPalace (open source) | 96.2% |
| Observational Memory (Mastra) | 95.4% |
| gpt-5-mini | 94.9% |
| Memento (bitemporal KG) | 92.4% |
| **Daimonion** | **90.8%** |
| Plain RAG | 70-75% |
| GPT-4o full context | 60-64% |
| ChatGPT with memory | ~58% |

### Multi-Session Gap (82.7%)

The weakest category. Semantic search finds answers when query terms overlap with evidence text. When connections are indirect (Entity A in Session 1, Entity B in Session 3, question about A+B relationship), semantic search misses. Improvement requires entity-resolved structured extraction with typed relationships across sessions.

### What LongMemEval Does NOT Test

- Nightly extraction pipeline quality (four-lens analysis, deduplication, supersession)
- Memory decay and correction mechanics
- Behavioral consistency (philosophical rules, identity)
- Session restoration quality (diary + MEMORY.md as briefing)
- Self-documentation (run reports, QA audit, wiki)
- Real-time capture (Stop hook)

---

## Memory Principles

1. **Never delete, only archive** — history has value even when faded
2. **Store WHY, not just WHAT** — rationale and rejected alternatives matter
3. **Three vertices, three purposes** — MemPalace (search), Graphiti (connections), Wiki (human reading)
4. **Karpathy is the reference library, not a tier** — always available alongside all tiers
5. **Synapsis is the sole writer of MEMORY.md** — auto memory disabled, compiled index only
6. **Sparse refs distinguish pending from excluded** — TBD vs N/A
7. **Retrieval follows the 7-step protocol** — context first, wiki last

# Daimonion Architecture v5

> An AI thinking partner with persistent memory, real-time capture,
> verified knowledge, and a philosophical operating system that never decays.

**Last updated:** 2026-04-13
**Platform:** Claude Code (Opus, Max subscription)

---

## The Four Components

| Name | Greek | Role |
|------|-------|------|
| **Daimonion** | δαιμόνιον | The system — the inner guiding voice |
| **Pythia** | Πυθία | The voice — Claude Code conversation interface |
| **Loci** | Loci (Method of Loci) | The memory — three storage vertices |
| **Synapsis** | Σύναψις | The connector — verification + enrichment + documentation |

---

## Memory Tiers

| Tier | Scope | Mechanism | Latency |
|------|-------|-----------|---------|
| **Active** | Current conversation | Claude Code context window | Instant — already in context |
| **Short-term** | Last 9 days | Diary + MEMORY.md (AAAK multi-vertex index) | Instant — loaded at session start |
| **Long-term** | Everything before | MemPalace (semantic + KG) + Graphiti (graph) | On demand — search when needed |

**Karpathy (Wiki)** is not a tier — it's the reference library. Always available across all tiers. Reports, compiled knowledge, audit trail.

Active memory is the context window itself. Claude Code handles it natively — no custom system needed.
Short-term is the diary (9-day AAAK index with multi-vertex refs into MemPalace, Graphiti, Wiki). Loaded at startup.
Long-term is MemPalace + Graphiti. Multi-dimensional search: semantic + KG facts + graph traversal.

### MEMORY.md — The Compiled Multi-Vertex Index

Each AAAK line is a hyperedge connecting related items across all three systems:
```
2026-04-12|auto.memory.DISABLED→Synapsis.sole.writer|mp:drawer_xxx|kg:auto_memory→disabled|gr:entity_yyy|wiki:decisions/memory-architecture|★★★★
```
One line. Pointers to MemPalace drawer, KG triple, Graphiti entity, Wiki page. One lookup, all three systems connected. Compiled by Synapsis (structure, not learned embeddings).

**Sparse ref convention:**
- `TBD` — Synapsis hasn't processed this yet, ref will be filled on next run (e.g. `gr:TBD`)
- `N/A` — Synapsis evaluated this entry and determined no ref is warranted in that system (e.g. `gr:N/A`)

Example (partial, pre-Synapsis):
```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing→revised|gr:TBD|wiki:TBD|★★★
```
Example (after Synapsis, fact excluded from Graphiti):
```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing→revised|gr:N/A|wiki:decisions/pricing-model|★★★
```

---

## Loci — Three Memory Vertices

Three stock open-source systems. No forks. No custom rebuilds. Connected by Synapsis.

### Vertex 1: MemPalace (Real-Time)

**Role:** What was said. Verbatim storage + quick facts. Real-time capture.

- **Technology:** ChromaDB + built-in SQLite knowledge graph
- **Access:** 19 MCP tools (search, traverse, find tunnels, KG query/add/invalidate/timeline, diary)
- **Organization:** Spatial — wings, rooms, halls, drawers
- **Input:** Raw text. It chunks, detects rooms, extracts entities, files drawers.
- **KG:** Subject → predicate → object triples with temporal validity (`valid_from`, `as_of`, `invalidate`)

**Captures during conversation:**
- Every exchange → `add_drawer` (via Stop hook, real-time)
- Explicit facts → `kg_add` ("remember this")
- Session diary → `diary_write` (milestones, decisions, session close)

### Vertex 2: Graphiti (Verified)

**Role:** What connects to what. Verified relationships. Post-QA only.

- **Technology:** Kuzu embedded graph DB
- **Access:** Graphiti MCP server (entity search, relations, multi-hop, recent, stats)
- **Input:** Structured entities + relations with metadata. Does NOT receive raw text.
- **Temporal:** `valid_at` / `expired_at` on relationships. Episodes for decision points.
- **Value:** Multi-hop queries that MemPalace KG can't express. "Chatzi → works on → Project Alpha → uses → pricing model → changed on → April 3."

**Fed by Synapsis only:**
- Real-time MemPalace KG entries → QA verified → promoted to Graphiti with full metadata
- Only clean, verified facts enter the deep graph

### Vertex 3: Wiki / Karpathy (Audit Trail)

**Role:** What was done about it. Reports, compiled knowledge, human-browsable.

- **Technology:** Obsidian-compatible markdown + wiki_ingester (routes raw/ → wiki structure)
- **Access:** File read, browsable in Obsidian
- **Input:** Documents dropped in `vault/raw/` → wiki_ingester routes to wiki subdirs
- **Structure:** projects/, decisions/, research/, concepts/, entities/, daily-briefings/

**Contains:**
- Synapsis QA reports (what was checked, what was flagged)
- Synapsis extraction reports (what went into Graphiti and why)
- Research reports (web search results compiled)
- Correction documents (flagged issues with detail)
- Synapsis run reports (full processing documentation)
- Everything Daimonion does produces a report. Every report goes here.

---

## Synapsis — The Connector (Σύναψις)

Connects the three vertices. Verifies. Enriches. Documents everything it does.

### Real-Time (During Conversation)

Pythia writes to MemPalace directly:
```
Exchange happens → Stop hook → mempalace_add_drawer (verbatim)
"Remember this" → mempalace_kg_add (fact)
Milestone reached → mempalace_diary_write (progress)
Session close → mempalace_diary_write (NEXT_ACTION, CONTEXT, refs)
```

### Batch (Synapsis Run — "Good Night" / Cron)

```
Step 0: EXTRACT DAILY LOGS
  └── JSONL → markdown (extract_claude_sessions.py)
  └── Skippable with --skip-extraction

Intelligence chain (sequential, Sonnet):
  Agent 1: EXTRACTOR — four-lens extraction from daily logs
  Agent 2: DEDUPLICATOR — compare against existing, supersession
  Agent 3: ANALYZER — pattern detection, drift, research flags
  Agent 4: RESEARCHER — web search on flagged topics (Brave API)

Information agents (parallel with intelligence chain):
  Agent 6: SPORTS (Haiku) — filtered by user interests
  Agent 7: NEWS (Haiku) — filtered by user interests
  Agent 8: WEATHER (API) — Open-Meteo, no LLM

Agent 5: COMPILER (runs after all above complete)
  └── Write memories → ChromaDB
  └── Write entities → Graphiti/Kuzu (GraphitiWriter, Haiku extracts)
  └── Promote high-significance memories → knowledge JSON
  └── Compile briefing → vault/daily-briefings/
  └── Update decay scores
  └── Build MEMORY.md (AAAK 9-day index)

Post-compiler:
  └── MemPalace mining (room detection)
  └── QA Auditor (9 checks on pipeline flow)
  └── Run report → vault/raw/ → wiki_ingester routes
  └── Diary entries (stats + Haiku-generated summary with multi-vertex refs)
```

### Principles
- **Synapsis verifies, never auto-corrects.** Flag and document. Humans decide.
- **Graphiti only gets what passed QA.** The deep graph stays clean.
- **Everything is documented.** Action log during processing, full report after.
- **All reports go through Karpathy.** The wiki is the audit trail.

---

## Retrieval Protocol

Order matters. Work down the layers:

```
Question asked
    │
    ├── 1. Context (active memory)
    │   └── Answer in current conversation? → done
    │
    ├── 2. MEMORY.md (short-term, 9 days)
    │   └── Answer in AAAK index? → done
    │   └── Follow ref: pointer for detail? → done
    │
    ├── 3. Diary
    │   └── Recent session notes? → done
    │
    ├── 4. MemPalace KG (quick facts)
    │   └── Entity lookup: kg_query → done
    │   └── Timeline: kg_timeline → done
    │
    ├── 5. MemPalace search (verbatim)
    │   └── Semantic search across drawers → done
    │
    ├── 6. Graphiti (deep connections)
    │   └── Multi-hop traversal → done
    │   └── Temporal query → done
    │
    └── 7. Wiki (compiled knowledge)
        └── file read or Obsidian browse → done
```

Most questions answered at steps 1-3. Steps 4-7 are for long-term recall, deep connections, and compiled knowledge.

---

## Data Flow

```
Conversation in Claude Code
    │
    ├── REAL-TIME ──────────────────────────────────
    │   │
    │   ├── Stop hook → mempalace_add_drawer (every exchange, verbatim)
    │   ├── Explicit → mempalace_kg_add (facts)
    │   └── Diary → mempalace_diary_write (milestones, session close)
    │
    ├── AUTOMATIC ──────────────────────────────────
    │   │
    │   └── Claude Code saves JSONL session files
    │
    └── SYNAPSIS (batch) ───────────────────────────
        │
        ├── Step 1: Read MemPalace KG + daily logs
        ├── Step 2: QA check → corrections → vault/raw/
        ├── Step 3: Extract + verify
        ├── Step 4: Validated entries → Graphiti
        ├── Step 5: Research → reports → vault/raw/
        ├── Step 6: Compile → MEMORY.md + skills
        ├── Step 7: Full report → vault/raw/
        └── Step 8: Health check
                │
                └── wiki_ingester routes all raw/ docs → wiki pages
```

---

## Session Protocol

### On Session Start
1. `date` — know the time. Non-negotiable.
2. `mempalace_diary_read` — the diary IS the briefing. Carries what happened, what's next, refs, social context.
3. MEMORY.md — loaded natively by Claude Code (AAAK 9-day index with refs)
4. Rules — loaded automatically by Claude Code
5. Skills — loaded on demand by conversation matching

### During Session
- Stop hook captures every exchange to MemPalace (real-time verbatim)
- Explicit saves via `kg_add` when asked to remember
- Diary entries for milestones and decisions

### On Session Close ("Good Night" / "Save")
```
mempalace_diary_write(agent_name="pythia", topic="session_close", entry=
  "SESSION:date|worked.on:...
   refs:kg_entries.and.drawer_ids.from.this.session
   rooms.touched:room1,room2
   NEXT_ACTION:exact.next.step
   BLOCKED:if.any
   CONTEXT:what.Chatzi.was.doing.when.he.left (optional)")
```
- NEXT_ACTION must be specific enough to start without digging
- CONTEXT enables context-aware re-engagement on return
- Trigger Synapsis if "Good Night" (full run)

---

## Identity System — Claude Code Native

### CLAUDE.md (~140 lines)
Identity only. Who Pythia is, how she thinks, values, shared language, system architecture brief, session start protocol, success metric.

### .claude/rules/ (always loaded)
| Rule | Lines | Purpose |
|------|-------|---------|
| behavioral-anchor.md | ~28 | Epistemic anchor: φαντασία → ἐξέτασις → νόησις. Named failure: προπέτεια (rash assent) |
| parrhesia.md | ~25 | Fearless truth-telling as care |
| elenchos.md | ~25 | Bilateral examination |
| gnothi-seauton.md | ~25 | Know what you know and don't |
| meden-agan.md | ~25 | Nothing in excess |
| memory-routing.md | ~15 | Retrieval protocol across Loci vertices |
| capture-rules.md | ~20 | What to capture, diary protocol |
| time-awareness.md | ~15 | Check date, session awareness |
| wiki-routing.md | ~15 | Three memory layers, when to use each |

### Skills (11 groups, on demand)
| # | Skill | Triggers |
|---|-------|----------|
| 1 | Strategic Thinking | trade-offs, both sides, should I, decision |
| 2 | Analytical Mode | analyze, evaluate, compare, decompose |
| 3 | Building Mode | architecture, codebase, implement, refactor |
| 4 | Communication Tuning | verbose, correction, emotional, understated |
| 5 | Business Context | pricing, strategy, market, consultancy |
| 6 | Project Awareness | timeline, priority, milestone, what's next |
| 7 | Voice & Telegram | voice mode, telegram, progressive response |
| 8 | Research Mode | investigate, search, competitor, current events |
| 9 | Memory & Recall | remember, what did we, when did, check memory |
| 10 | Brainstorm Mode | what if, idea, explore, options |
| 11 | Synapsis | good night, save, run synapsis (user-invocable) |

Each skill: `SKILL.md` (stable instructions) + supporting files (evolve via Synapsis enrichment).

---

## Three Systems, Stock, Connected

| | MemPalace | Graphiti | Wiki/Karpathy |
|---|---|---|---|
| **What it stores** | Verbatim + quick facts | Verified relationships | Reports + compiled knowledge |
| **When it's written** | Real-time (during conversation) | Batch (post-QA via Synapsis) | Batch (reports via wiki_ingester) |
| **How it's searched** | 19 MCP tools + KG tools | Graphiti MCP server (7 tools) | file read, Obsidian browse |
| **Input format** | Raw text | Structured entities + relations | Documents in raw/ |
| **Quality guarantee** | Fast, imperfect | QA-verified only | Compiled from verified sources |
| **Stock tool** | MemPalace MCP server | Graphiti + Kuzu | wiki_ingester + Obsidian |

**Principle:** Use stock. Don't fork. Synapsis connects.

---

## Key Design Decisions (2026-04-12)

1. **Real-time capture via MemPalace.** Stop hook writes every exchange. No extraction script needed for verbatim.
2. **MemPalace KG for quick facts.** `kg_add` during conversation. Lightweight, immediate, searchable.
3. **Graphiti receives only QA-verified entries.** Synapsis checks, flags, documents. Clean graph.
4. **Wiki is the audit trail.** Every process produces a report. Every report goes through wiki_ingester.
5. **Synapsis documents itself.** Action log during processing, full report after. No black box.
6. **Corrections are flagged, not auto-fixed.** Document → raw/ → wiki. Humans decide.
7. **Diary replaces session-start-briefing.** One system. NEXT_ACTION + CONTEXT + refs.
8. **MEMORY.md written by Synapsis.** AAAK 9-day index. Native Claude Code loading. Auto memory disabled.
9. **Three stock systems, one lightweight custom.** MemPalace, Graphiti (stock). Wiki_ingester (custom, replaces second-brain). Synapsis is the main custom code.
10. **Multi-dimensional search.** MemPalace (semantic + KG), Graphiti (graph), Wiki (compiled). Not one-dimensional.
11. **Context is precious.** ~565 lines always loaded. Everything else on demand via refs and search.
12. **Three memory tiers.** Active (context window), Short-term (9-day diary + MEMORY.md), Long-term (MemPalace + Graphiti). Karpathy alongside all tiers.
13. **Retrieval protocol.** Context first → MEMORY.md → diary → KG → search → graph → wiki. Order matters.
14. **MEMORY.md as compiled multi-vertex index.** Each AAAK line is a hyperedge with refs into all three systems. Structure, not learned embeddings. HeLLM pattern at index scale.
15. **Sparse refs: TBD vs N/A.** `TBD` = Synapsis hasn't processed yet (pending). `N/A` = Synapsis evaluated, no ref warranted (excluded). Distinguishes "not yet reached" from "reached and decided against."

---

## Current State (2026-04-13)

### Working
- [x] Real-time capture hook (Stop hook → `add_drawer`)
- [x] MemPalace KG (`kg_add` / `kg_query` tested)
- [x] Diary read/write via MCP
- [x] MemPalace semantic search (19 MCP tools)
- [x] Synapsis orchestrator — single entry point, one command
- [x] Synapsis QA auditor (9 checks post-pipeline)
- [x] Synapsis action log + run reports → vault/raw/ → wiki
- [x] Synapsis writing to Graphiti (GraphitiWriter.write_episode via Haiku)
- [x] MEMORY.md compiler (AAAK 9-day index, 190 entries at native path)
- [x] Wiki ingester (routes vault/raw/ → wiki structure)
- [x] Graphiti MCP server (7 tools: search, relations, multi-hop, recent, stats, fact_add, fact_query)
- [x] Cron automation (3 AM daily)
- [x] Step 0 (daily log extraction) integrated into orchestrator
- [x] Backfill complete (Mar 30 – Apr 12: 227 memories, 116 knowledge, 789 entities)
- [x] Brave API key configured
- [x] 148 tests passing
- [x] Rules loaded (9 files in .claude/rules/)
- [x] Skills loaded (11 in .claude/skills/)
- [x] Auto memory disabled

### Not Built
- [ ] The Clock (conversational tempo, gap detection)
- [x] LongMemEval benchmark — 90.8% (500 questions, oracle dataset). See docs/longmemeval-benchmark-results.md

---

## Success Criteria

- [ ] New session starts → diary + MEMORY.md gives full context without archaeology
- [x] "What did we decide about X?" → answer found via multi-dimensional search (MemPalace + Graphiti + Wiki)
- [x] Every Synapsis run produces a wiki report documenting what it did (13 reports in vault/synapsis-runs/)
- [x] Graphiti entities extracted by Haiku from Sonnet-extracted memories (single write path)
- [x] Real-time capture means no conversation is lost between sessions (Stop hook → add_drawer)
- [ ] Total startup context ≤ 600 lines (CLAUDE.md + rules + MEMORY.md)
- [x] Three stock systems + one lightweight custom connector

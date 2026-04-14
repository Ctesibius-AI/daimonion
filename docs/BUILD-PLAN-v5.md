# Build Plan v5 — Wire the Triangle

**Created:** 2026-04-12
**Completed:** 2026-04-13 — all 7 phases done
**Supersedes:** BUILD-PLAN-v4 (2026-04-11) — phases 1-5 done, phase 6 deferred
**Goal:** Connect three stock systems (MemPalace, Graphiti, Wiki) via Synapsis. Real-time capture. Multi-vertex index. Full observability.

---

## What's Done

### From v4 + April 12 session
- [x] CLAUDE.md trimmed to ~140 lines
- [x] 9 rules in `.claude/rules/` (behavioral anchor, 4 philosophy, memory routing, capture rules, time awareness, wiki routing)
- [x] 11 skills in `.claude/skills/`
- [x] Auto memory disabled
- [x] Diary protocol redesigned (refs, NEXT_ACTION, CONTEXT)
- [x] Real-time capture hook (Stop hook → `mempalace_add_drawer`)
- [x] MemPalace KG tested and working (`kg_add`, `kg_query`)
- [x] Brave API key migrated
- [x] Parser bug fixed (synapsis_extractor format mismatch)
- [x] 148 tests passing
- [x] Architecture v5 document written

### April 13 session (BUILD-PLAN-v5 execution)
- [x] Phase 1: Pipeline consolidated (9 night_* files archived, one entry point)
- [x] Phase 2a: Step 0 integrated, existing pipeline routed through single entry
- [x] Phase 2b: Action log + report generation + wiki ingestion wired
- [x] Phase 3: MEMORY.md compiler built, 190 entries at native Claude Code path
- [x] Phase 4: Graphiti MCP server (7 tools, registered in Pythia .mcp.json)
- [x] Phase 5: wiki_ingester.py built (replaces second-brain, routes vault/raw/ → wiki)
- [x] Phase 6: Cron set (3 AM daily, replaces 3 stale entries)
- [x] Phase 7: Backfill complete (Mar 30 – Apr 12: 227 memories, 116 knowledge, 789 graph entities)
- [x] QA: docs updated, stale references removed, data integrity verified
- [x] Phase 8 (2026-04-13 evening): Graphiti unified to single write path (GraphitiWriter/Haiku), DirectGraphWriter removed, KB promotion step removed (redundant), diary Haiku summary verified working, extractor dedup rule added, full reprocessing started

---

## Phase 1: Consolidate Synapsis

Remove duplicate pipelines. One entry point.

1. Keep `src/processors/synapsis_orchestrator.py` (the complete one)
2. Keep `scripts/run_synapsis.py` (uses orchestrator)
3. Delete or archive: `run_synapsis.py` (root — incomplete), `run_night.py` (root — incomplete)
4. Delete or archive: all `night_*` files in `src/processors/` (old naming)
5. Update `scripts/run_synapsis.py` to load `.env` (currently doesn't)
6. Verify: one command runs the full pipeline

---

## Phase 2a: Rewire Existing Pipeline

Route existing working steps through the single consolidated entry point. No new logic. Steps numbered to match final architecture (2, 7 added in Phase 2b).

1. **Daily log extraction** — JSONL → markdown (existing `extract_claude_sessions.py`). Eventually replaced by real-time capture, but needed for backfill.
2. **READ** — Read MemPalace KG entries from today (`kg_query` or direct ChromaDB). Read daily logs.
3. **EXTRACT + VERIFY** — Extract entities, relations, decisions from daily logs (existing extractor, fixed parser). Cross-reference with existing Graphiti content. Deduplicate, detect supersessions.
4. **WRITE TO GRAPHITI** — Each memory → GraphitiWriter.write_episode (Haiku extracts entities + relationships). Single write path.
5. **RESEARCH** (existing, now with Brave key) — Web search on flagged topics. Compile reports → `vault/raw/`.
6. **COMPILE** — Build MEMORY.md as multi-vertex index (AAAK lines with mp:/kg:/gr:/wiki: refs). Sparse ref convention: `TBD` (pending) / `N/A` (evaluated, excluded). Write to native Claude Code path. Update decay scores.
7. **HEALTH CHECK** (existing) — All subsystems operational.

**Done when:** One command runs the existing pipeline end-to-end through a single entry point.

---

## Phase 2b: Add Intelligence Layer

Build on top of the working pipeline from 2a. New capabilities only.

### Step 1 addition: Action log
- Start action log at pipeline start
- Each subsequent step logs its results to the action log

### Step 2: QA CHECK (new)
- Compare KG entries against daily log content
- Flag missed items, flag incorrect entries
- Create correction document → `vault/raw/` if needed
- Note findings in diary
- Log results

### Step 7: DOCUMENT (new)
- Compile full run report from action log
- Drop report in `vault/raw/`
- Write diary entry

**Done when:** QA step runs, action log captures all steps, every run produces a report in `vault/raw/`.

---

## Phase 3: MEMORY.md at Native Path

1. Find/create `~/.claude/projects/-Users-pythia-gr-daimonion-pythia/memory/`
2. Update Synapsis compiler to write MEMORY.md there
3. Format: AAAK multi-vertex index, ≤200 lines, 9-day rolling
4. Each line carries refs: `mp:drawer_id|kg:triple_id|gr:entity_id|wiki:page_path`
5. Sparse refs: `TBD` (pending Synapsis) / `N/A` (evaluated, excluded) — see ARCHITECTURE.md Decision 15
6. Verify native loading at session start
7. Remove old `hot_cache.md` reference from startup

---

## Phase 4: Graphiti Search (MCP Tool)

Expose Graphiti/Kuzu queries during conversation via MCP tool. Same interface pattern as MemPalace — consistent, works naturally in conversation without bash workarounds.

1. Build MCP tool wrapping Kuzu queries (multi-hop traversal, temporal, entity lookup)
2. Register in MCP config alongside MemPalace
3. Verify Pythia can query Graphiti in conversation the same way she queries MemPalace

---

## Phase 5: Wiki Pipeline

1. Built `wiki_ingester.py` (replaces planned second-brain tool)
2. Routes `vault/raw/` documents by filename pattern → wiki subdirs
3. Full loop verified: Synapsis report → `raw/` → wiki_ingester → `synapsis-runs/`
4. Vault index auto-regenerated with Obsidian-compatible wikilinks

---

## Phase 6: Cron

1. Set up cron for Synapsis: daily at 3 AM
2. Include daily log extraction as step 0
3. Verify it runs unattended
4. Health check alerts if a run fails

---

## Phase 7: Backfill Missing Days

1. Process April 3-10 through the updated pipeline (sequentially)
2. Verify deduplication catches overlaps
3. Verify Graphiti entities merge correctly across days
4. Check MemPalace for expected content from each day

---

## Dependency Order

```
Phase 1 (consolidate) ──→ Phase 2a (rewire existing) ──→ Phase 2b (intelligence)
                                                       ──→ Phase 3 (MEMORY.md)
                                                       ──→ Phase 4 (Graphiti search — MCP tool)
                                                       ──→ Phase 5 (Wiki pipeline)
                                                                     │
                                                           Phase 6 (cron) ──→ Phase 7 (backfill)
```

Phase 1 first (can't rewire a pipeline with three copies).
Phase 2a next — get existing steps running through one entry point.
Phases 2b, 3-5 can run in parallel after 2a (2b adds intelligence, 3-5 are independent wiring).
Phase 6 after the pipeline is proven.
Phase 7 last — backfill through the final pipeline.

---

## Success Criteria

- [x] One Synapsis pipeline, one entry point, one command
- [x] Every run produces a report in `vault/raw/`
- [x] MEMORY.md at native path, multi-vertex AAAK format, loaded at startup
- [x] Graphiti queryable during conversation (MCP server, 7 tools)
- [x] Wiki pages generated from Synapsis reports (wiki_ingester.py)
- [x] Cron runs nightly without intervention
- [x] Missing days processed, no data gaps (Mar 30 – Apr 12 backfilled)
- [ ] New session starts → diary + MEMORY.md = full context, no archaeology

# Implementation Plan: Knowledge System Unification

**Created:** 2026-04-13
**Decision:** Graphiti/Kuzu = single source for structured knowledge. MemPalace = verbatim only.
**Prerequisite reading:** `docs/pending-knowledge-unification.md`

---

## Current State (verified April 13)

| System | Count | Purpose | Status |
|--------|-------|---------|--------|
| Knowledge JSON (`~/.daimonion/knowledge/*.json`) | 91 files | Free-text facts with category + confidence + embedding | Staging area — Synapsis writes, 10+ files read |
| MemPalace KG (ChromaDB `room=knowledge_graph`) | 4 triples, 7 entities | Quick-lookup triples via MCP | Nearly empty, no pipeline integration |
| Graphiti/Kuzu | 789 entities, 1,409 relations, 199 episodes | Structured graph with temporal metadata | Active, single write path via Haiku |

**The problem:** Three stores, no reconciliation. Knowledge JSON and Graphiti both receive Synapsis output independently. MemPalace KG has MCP tools but almost no data and no pipeline feeding it.

---

## Architecture Target

```
Synapsis extracts facts
        │
        ▼
Knowledge JSON (staging — unchanged)
        │
        ▼
Graphiti/Kuzu (single source for structured knowledge)
        │
        ├── graphiti_entity_search    (existing — read)
        ├── graphiti_entity_relations (existing — read)
        ├── graphiti_multi_hop        (existing — read)
        ├── graphiti_recent           (existing — read)
        ├── graphiti_stats            (existing — read)
        ├── graphiti_fact_add         (NEW — write, simple triple interface)
        └── graphiti_fact_query       (NEW — read, fast entity fact lookup)

MemPalace ChromaDB = verbatim drawers + diary ONLY (no KG triples)
```

---

## Implementation Steps

### Step 1: Add write + fast-lookup tools to Graphiti MCP server

**File:** `src/mcp/graphiti_server.py`

**Add two new tools:**

#### 1a. `graphiti_fact_add` — Simple triple write

Purpose: Let Pythia record structured facts during conversation (replaces `mempalace_kg_add` for knowledge).

```python
@mcp.tool()
def graphiti_fact_add(
    subject: str,
    predicate: str,
    object: str,
    valid_from: str = "",
) -> str:
    """Add a fact to the knowledge graph as a Kuzu entity + relationship.

    Args:
        subject: The entity doing/being something (e.g. "Project Alpha").
        predicate: The relationship (e.g. "pricing_model").
        object: The connected entity (e.g. "subscription-based").
        valid_from: When this became true (YYYY-MM-DD, optional).
    """
```

**Implementation approach:**
- Use direct Kuzu writes (not Graphiti's `add_episode`, which is heavy and uses Haiku for extraction — overkill for a single triple)
- Check if subject Entity node exists → create if not (with `group_id='daimonion'`, `labels=['concept']`, `created_at=now`)
- Check if object Entity node exists → create if not
- Create RelatesToNode_ between them with: `name=predicate`, `fact=f"{subject} {predicate} {object}"`, `valid_at=valid_from or now`, `expired_at=NULL`
- Return confirmation string with entity names

**Important Kuzu detail:** RelatesToNode_ is a *node table*, not a relationship table. The connection pattern is:
```
(Entity)-[:RELATES_TO]->(RelatesToNode_)-[:RELATES_TO]->(Entity)
```
So creating a triple means:
1. Ensure both Entity nodes exist
2. Create a RelatesToNode_ node
3. Create two RELATES_TO edges (source→rel_node, rel_node→target)

Study the existing `graphiti_entity_relations` query (line 86) for the exact pattern. The RELATES_TO edge table already exists — check its schema before writing:
```python
conn.execute('CALL TABLE_INFO("RELATES_TO") RETURN *')
```

**Deduplication:** Before creating, check if an active (non-expired) triple with the same subject+predicate+object already exists. If so, return "already exists" instead of duplicating.

#### 1b. `graphiti_fact_query` — Fast entity lookup

Purpose: Quick "what do we know about X?" during conversation (replaces `mempalace_kg_query`).

```python
@mcp.tool()
def graphiti_fact_query(
    entity: str,
    as_of: str = "",
) -> str:
    """Quick lookup: all facts about an entity. Returns typed relationships.

    Args:
        entity: Entity name to query (case-insensitive partial match).
        as_of: Only show facts valid at this date (YYYY-MM-DD, optional).
    """
```

**Implementation approach:**
- Query both outgoing and incoming relationships (copy pattern from `graphiti_entity_relations`)
- Add temporal filter: `WHERE e.expired_at IS NULL` (already in existing queries) + optional `AND e.valid_at <= $as_of` if as_of provided
- Format output as: `subject → predicate → object (since YYYY-MM-DD)`
- Use case-insensitive partial match on entity name (like `graphiti_entity_search` does)
- Include entity summary if available

**How this differs from `graphiti_entity_relations`:** The existing tool returns raw relationship data with episodes. The new tool returns *facts* in a human-readable format optimized for quick conversation lookups, with temporal filtering. Think of it as the "conversation-speed" version.

---

### Step 2: Remove KG write step from orchestrator

**File:** `src/processors/synapsis_orchestrator.py`

**Delete lines 693-731** (the `# 2b. Write entities as MemPalace KG triples` block).

This block:
- Imports `mempalace.palace.get_collection`
- Iterates entities and their relations
- Writes triples to ChromaDB with `room=knowledge_graph` metadata
- Currently produces 0 entries (never ran since being added)

**Also remove:**
- Any references to `kg_triples_written` in the result dict (search the file — it appears at lines 727, 731, and in the diary ref builder at line 348)
- The `kg:{kg_count}_triples` ref part in the diary entry builder (line 348) — replace with just removing it or making it `gr:{gr_entities}_entities` only

**Do NOT remove:**
- Step 2 (`_write_all_to_graphiti`) at line 685-691 — that's the real Graphiti write path that stays
- Any Graphiti writer references

---

### Step 3: ~~Knowledge JSON → Graphiti promotion~~ — SUPERSEDED

**Status:** Removed (2026-04-13 evening session).

**What changed:** Step 2 (`_write_all_to_graphiti`) was rewritten to use `GraphitiWriter.write_episode` (Haiku-powered) instead of `DirectGraphWriter` (shallow structured nodes). Every memory now goes through Haiku entity extraction in Step 2.

**Why Step 3 is no longer needed:** KB entries are distilled FROM the same memories that Step 2 already processes. Promoting KB entries separately would double-write the same content to Graphiti. The `_promote_knowledge_to_graphiti` method still exists in the codebase but is no longer called from the pipeline.

**The old problem:** DirectGraphWriter produced shallow nodes (no real entity extraction). Step 3/8b was the only path to rich Graphiti entities via Haiku. With Step 2 now using Haiku, that gap is closed.

---

### Step 4: Verify fast lookup performance

**Manual verification step — not code.**

After Steps 1-3, run:
```python
# From daimonion/.venv
python -c "
from src.mcp.graphiti_server import graphiti_fact_query
import time
t0 = time.time()
result = graphiti_fact_query('Project Alpha')
print(f'Time: {time.time()-t0:.3f}s')
print(result)
"
```

**Acceptance criteria:**
- `graphiti_fact_query` returns in < 500ms for single entity lookup
- Results include temporal metadata (valid_from)
- Results match what's in Graphiti (cross-check with `graphiti_entity_relations`)

If > 500ms: add a Kuzu index on `Entity.name` (probably already exists from Graphiti's `build_indices_and_constraints`).

---

### Step 5: Update capture-rules.md

**File:** `daimonion-pythia/.claude/rules/capture-rules.md`

**Replace lines 19-24:**

```markdown
## How to Write
Use MCP tools for memory storage:
- Memories (verbatim): `mempalace_add_drawer` (content, room, wing)
- Knowledge facts (structured): `graphiti_fact_add` (subject, predicate, object)
- Diary entries: `mempalace_diary_write` (agent_name, entry, topic)

For batch operations or legacy access:
~~~bash
~/daimonion/.venv/bin/python ~/daimonion/scripts/pythia_tools.py save_memory "content" collection
~/daimonion/.venv/bin/python ~/daimonion/scripts/pythia_tools.py save_knowledge "fact" category
~~~
```

**Note:** Keep the bash commands as fallback — `save_knowledge` still writes to JSON staging, which is a valid entry point. The MCP tools become primary.

---

### Step 6: CLAUDE.md Changes 2-4 (now unblocked)

**File:** `daimonion-pythia/CLAUDE.md`

Follow `docs/planned-changes-claude-md.md` exactly:

**Change 2:** Cut the Pipeline Tools section (lines 107-116). The bash commands are now documented in capture-rules.md as fallback, and MCP tools are primary.

**Change 3:** Compress System Architecture section (lines 93-127) to ~20 lines:
- Keep: directory layout (3 lines), Loci description (3 lines), Synapsis one-liner (1 line)
- Keep: Session Start protocol (lines 118-126) — MUST stay, it's unconditional
- Remove: Pipeline Tools block (gone via Change 2)
- Tighten: Synapsis description to one line

**Change 4:** Natural outcome. Target: ~115 lines total.

---

## Files Modified (summary)

| File | Change | Step |
|------|--------|------|
| `src/mcp/graphiti_server.py` | Add `graphiti_fact_add` + `graphiti_fact_query` | 1 |
| `src/processors/synapsis_orchestrator.py` | Remove ChromaDB KG write, rewrite Step 2 to use GraphitiWriter (Haiku), remove Step 8b (redundant KB promotion) | 2, 3 |
| `daimonion-pythia/.claude/rules/capture-rules.md` | Update "How to Write" to MCP-first | 5 |
| `daimonion-pythia/CLAUDE.md` | Compress architecture, cut pipeline tools | 6 |

## Files NOT modified (and why)

| File | Why |
|------|-----|
| `src/memory/store.py` | Knowledge JSON stays as staging — `save_knowledge()` still needed |
| `src/memory/retrieval.py` | Already uses Graphiti when available, JSON as fallback — correct |
| `src/processors/synapsis_extractor.py` | Still writes to Knowledge JSON — correct (staging) |
| `src/processors/synapsis_compiler.py` | Reads Knowledge JSON for wiki compilation — still valid |
| `src/processors/memory_index_compiler.py` | Reads Knowledge JSON for MEMORY.md — still valid |
| `src/processors/qa_auditor.py` | Audits Knowledge JSON — still valid |
| `src/processors/health_monitor.py` | Checks Knowledge JSON health — still valid |
| `scripts/pythia_tools.py` | Stays as CLI fallback |
| MemPalace MCP server | Stock tool — not ours to modify. `mempalace_kg_*` tools still work but become secondary |

## Risks

1. **Graphiti write_episode is slow** (~3-5s per episode with Haiku extraction). Step 2 now runs Haiku per memory — a day with 15 kept memories adds ~45-75s. Acceptable for nightly batch; monitor for heavier days.

2. **Direct Kuzu writes in Step 1a may conflict with Graphiti's schema expectations.** The RelatesToNode_ pattern is specific to Graphiti's internals. Test thoroughly — if Kuzu writes break Graphiti's traversal, fall back to using `write_episode` even for single triples (slower but safe).

3. **Single Graphiti write path means no fallback.** If GraphitiWriter fails, zero entities are written for that day. The old DirectGraphWriter was zero-API and always worked. Monitor Haiku availability.

## Execution Order

Steps 1 and 2 are the core work. Step 3 is superseded. Steps 4-6 are validation and cleanup.

Do steps 1 and 2 together (they're independent). Then 4 (validation). Then 5 and 6 together (both are doc updates).

**Do not skip Step 4.** If fast lookup is too slow, the whole premise fails and we need a caching strategy.

## Changes Made (2026-04-13 evening)

| Change | What | Why |
|--------|------|-----|
| Step 2 rewritten | `_write_all_to_graphiti` uses GraphitiWriter.write_episode (Haiku) instead of DirectGraphWriter | Single quality path — Haiku extracts real entities from memories |
| Step 8b removed | `_promote_knowledge_to_graphiti` no longer called | Redundant — memories already go through Haiku in Step 2 |
| DirectGraphWriter dead code | `_ensure_direct_writer` removed from orchestrator | No callers remain |
| Extractor prompt | Added "do not extract same fact twice" rule | Reduce within-day duplication |
| Diary summary | Haiku LLM summary step (Option B) already implemented | Replaces mechanical concatenation — verified working |

## Test Plan

1. After Step 1: call `graphiti_fact_add("test_entity", "is_a", "test")` and verify with `graphiti_fact_query("test_entity")`. Clean up test data.
2. After Step 2: run `python -m pytest tests/ --tb=line -q` — all 148 tests should pass. Verify no references to `kg_triples_written` remain except in test fixtures.
3. After Step 3: run Synapsis for one date, verify KB entries appear in Graphiti: `graphiti_entity_search("Daimonion")` should show promoted facts.
4. After Step 6: `wc -l daimonion-pythia/CLAUDE.md` — should be ≤ 120 lines.

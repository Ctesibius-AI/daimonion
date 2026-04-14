# Pending: Knowledge System Unification

**Created:** 2026-04-13
**Status:** Decision made and partially implemented (2026-04-13). Graphiti is single source. Step 2 rewritten to use Haiku. Step 8b (KB promotion) removed as redundant. Diary summary uses Haiku (Option B). Reprocessing March 30–April 12 in progress.
**Priority:** Next architecture session. Not urgent — system works as-is for daily use.

---

## The Problem

Three knowledge systems existed. None talked to each other.

| System | Format | Writer | Reader | Count | Status |
|--------|--------|--------|--------|-------|--------|
| Knowledge JSON | Free-text + category + confidence | Synapsis extractor, pythia_tools.py | 10+ pipeline files | 91 files | Stays as extraction staging |
| MemPalace KG | Subject→predicate→object triples | MCP kg_add (manual only) | MCP kg_query, kg_timeline | 0 entries | Being eliminated — rewire to Graphiti |
| Graphiti/Kuzu | Entities + relationships + episodes | Synapsis → GraphitiWriter.write_episode (Haiku) | Graphiti MCP server (8 tools) | 789 entities, 1,409 relations | Single source (active) |

## What Was Wrong

- Knowledge JSON and Graphiti both received Synapsis output independently — no reconciliation
- MemPalace KG had MCP tools (kg_add, kg_query) but 0 entries and no pipeline integration
- A KG write step was built that would have written to MemPalace ChromaDB, creating a third parallel store
- The retrieval protocol in ARCHITECTURE.md described MemPalace KG as "step 4" — this was aspirational, not implemented in code
- `retrieval.py` has two backends (Graphiti + JSON fallback), neither references MemPalace KG

## Decision (2026-04-13)

**Graphiti as single source for structured knowledge.** MemPalace for verbatim. No parallel store.

- Knowledge JSON stays as extraction staging (Synapsis writes here first, 10+ pipeline files depend on it)
- Graphiti is the destination for verified structured knowledge (already has 789 entities)
- MemPalace KG (ChromaDB triples) — eliminate as separate store, rewire kg_query/kg_add to query Graphiti instead
- The Graphiti MCP server gets kg_add/kg_query equivalents (simple entity create/lookup backed by Kuzu)

**Rationale:** Building a parallel store "just in case" is engineering for fear. Graphiti has 789 entities and works. One system for structured knowledge, one for verbatim.

## Current Gap (livable)

91 Knowledge JSON files are only accessible via `pythia_tools.py` bash command during conversation. No MCP tool. Functional but not elegant.

## Implementation Plan

1. Add entity create + simple lookup tools to Graphiti MCP server — **done** (graphiti_fact_add, graphiti_fact_query)
2. Remove KG write step from orchestrator — **done**
3. ~~Build Knowledge JSON → Graphiti promotion step~~ — **superseded**: Step 2 rewritten to use GraphitiWriter.write_episode (Haiku). Memories go through Haiku directly. Separate KB promotion removed as redundant.
4. Verify quick lookups via Graphiti MCP are fast enough for conversation — **pending**
5. Update capture-rules.md to use Graphiti MCP instead of pythia_tools.py — **pending**
6. Then CLAUDE.md Changes 2-4 become safe to implement — **pending**

## How This Was Found

During session restoration testing (April 13), Pythia identified that the diary summary was missing knowledge entries. Investigation traced the issue to the diary builder, which was fixed with an LLM summary step. The deeper investigation revealed the three-system duplication. The dev team initially described MemPalace KG as "fast path retrieval (step 4 in protocol)" — Pythia correctly identified this as προπέτεια (the retrieval protocol exists in the architecture doc but not in code). The corrected assessment led to the decision to unify.

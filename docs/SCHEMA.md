# Daimonion Schema Reference

**Last updated:** 2026-04-14

Every persistent data structure used in the Daimonion system. Data lives in three storage vertices plus a compiled index:

| Vertex | Technology | Location |
|--------|-----------|----------|
| **MemPalace** | ChromaDB vectors + SQLite KG | `~/.daimonion/mempalace/` |
| **Graphiti** | Kuzu embedded graph DB | `~/.daimonion/graph/daimonion.kuzu` |
| **Wiki/Karpathy** | Obsidian-compatible markdown | `~/.daimonion/vault/` |
| **MEMORY.md** | Compiled index (AAAK format) | `~/.claude/projects/.../memory/MEMORY.md` |

Legacy JSON files (`memories/*.json`, `knowledge/*.json`) remain for backward compatibility. Both formats documented below.

All writes are atomic (write to `.tmp`, then `os.replace`). All timestamps are ISO 8601 UTC. Nothing is ever deleted — only archived.

---

## 1. Memory JSON Record

**Location:** `~/.daimonion/memories/<id>.json`
**Naming:** Filename is the `id` field with `.json`. IDs are UUIDs (from daytime `MemoryStore.save_memory`) or structured IDs like `mem_20260408_001` (from Synapsis).
**Created by:** `MemoryStore.save_memory()` (daytime) or `SynapsisExtractor.run()` (nightly extraction)

```json
{
  "id": "mem_20260408_001",
  "content": "Chatzi decided to freeze non-critical merges until mobile release cut on March 5",
  "collection": "procedural",
  "created_at": "2026-04-08T10:30:00+00:00",
  "source_date": "2026-04-08",
  "source_conversation_date": "2026-04-08",
  "access_count": 3,
  "last_accessed": "2026-04-10T14:00:00+00:00",
  "correction_factor": 1.0,
  "decay_score": 0.72,
  "archived": false,
  "embedding": [0.012, -0.034, 0.087, "... (384 floats)"],
  "entities": ["Chatzi"],
  "significance": "high",
  "_graphiti_synced": true
}
```

### Field Reference

| Field | Type | Computed | Description |
|-------|------|----------|-------------|
| `id` | `str` | yes | Unique identifier. UUID from daytime writes, or `mem_YYYYMMDD_NNN` from Synapsis. |
| `content` | `str` | no | The memory text. 1-2 sentences. |
| `collection` | `str` | no | One of: `identity`, `procedural`, `insights`, `episodic`, `sessions`. |
| `created_at` | `str` (ISO 8601) | yes | UTC timestamp when written to disk. |
| `source_date` | `str` (YYYY-MM-DD) | no | Date of the original conversation. |
| `source_conversation_date` | `str` (YYYY-MM-DD) | no | Same as `source_date` in most cases. Cross-referencing. Optional. |
| `access_count` | `int` | yes | Number of times retrieved. Starts at 0. |
| `last_accessed` | `str` (ISO 8601) or `null` | yes | Timestamp of most recent retrieval. Null if never accessed. |
| `correction_factor` | `float` | yes | `1.0` = current, `0.3` = superseded, `0.1` = corrected/wrong. |
| `decay_score` | `float` | yes | 0.0-1.0. Computed by `DecayScorer`. Below 0.05 → archived. |
| `archived` | `bool` | yes | True when `decay_score` drops below 0.05 and age > 60 days. Never deleted. |
| `embedding` | `list[float]` | yes | 384-dimensional from `all-MiniLM-L6-v2`. Used for deduplication and retrieval. |
| `entities` | `list[str]` | no | Project/system/person names. Optional — present when extracted by Synapsis. |
| `significance` | `str` | no | `high`, `medium`, or `low`. Optional — present when extracted by Synapsis. |
| `_graphiti_synced` | `bool` | yes | True after synced to Kuzu graph. Optional. |

### Collection Values

| Collection | Purpose | Decay Rate/Day |
|------------|---------|----------------|
| `identity` | Personal traits, preferences, relationship patterns | 0.999 (slow) |
| `procedural` | Technical decisions, architecture choices | 0.997 (slow) |
| `insights` | Strategic observations, business conclusions | 0.993 (medium) |
| `episodic` | Specific events, conversations | 0.985 (normal) |
| `sessions` | Conversation summaries (short-lived) | 0.960 (fast) |

---

## 2. Knowledge JSON Record

**Location:** `~/.daimonion/knowledge/<id>.json`
**Naming:** Filename is the `id` field with `.json`. IDs are UUIDs or `kb_YYYYMMDD_NNN`.
**Created by:** `MemoryStore.save_knowledge()` (daytime) or `SynapsisExtractor.run()` (nightly promotion)

```json
{
  "id": "kb_20260408_001",
  "fact": "Project Alpha pricing targets 250-300 euro per month",
  "category": "business",
  "source_memories": ["mem_20260408_001"],
  "created_at": "2026-04-08T03:10:00+00:00",
  "source_date": "2026-04-08",
  "confidence": 1.0,
  "entities": ["Project Alpha"],
  "domain": "business",
  "embedding": [0.012, -0.034, 0.087, "... (384 floats)"],
  "promoted_to_graphiti": true,
  "_graphiti_synced": true
}
```

### Field Reference

| Field | Type | Computed | Description |
|-------|------|----------|-------------|
| `id` | `str` | yes | Unique identifier. UUID or `kb_YYYYMMDD_NNN`. |
| `fact` | `str` | no | The factual statement. 1-2 sentences. |
| `category` | `str` | no | Free-form. Common values: `general`, `business`, `technical`, `personal`. Used by daytime API. |
| `domain` | `str` | no | Semantic domain: `technical`, `business`, `personal`. Used by Synapsis extraction. Optional. |
| `source_memories` | `list[str]` | no | Memory IDs this knowledge was derived from. Empty if created directly. |
| `created_at` | `str` (ISO 8601) | yes | UTC timestamp when written. |
| `source_date` | `str` (YYYY-MM-DD) | no | Date of source conversation. Optional — present when created by Synapsis. |
| `confidence` | `float` | no | 0.0-1.0. Default 1.0. |
| `entities` | `list[str]` | no | Entity names mentioned. Optional. |
| `embedding` | `list[float]` | yes | 384-dimensional. Used for deduplication and retrieval. |
| `promoted_to_graphiti` | `bool` | yes | True when this fact has been written to Kuzu as an entity or relationship. |
| `_graphiti_synced` | `bool` | yes | Internal flag for graph sync status. Optional. |

**Note:** `category` (from daytime API) and `domain` (from Synapsis) serve similar roles. Both may be present.

---

## 3. Graphiti / Kuzu Schema

**Location:** `~/.daimonion/graph/daimonion.kuzu`
**Initialized by:** Graphiti's `build_indices_and_constraints()` (called during GraphitiWriter initialization)
**Written by:** `GraphitiWriter.write_episode` (Synapsis batch writes via Haiku entity extraction) and `graphiti_server.py` (MCP tool writes)

The schema uses Graphiti's hypergraph pattern: relationships are modeled as intermediate nodes (RelatesToNode_) with edges connecting source Entity → RelatesToNode_ → target Entity.

### Entity (Node Table)

Represents a person, project, concept, or thing.

| Column | Type | Description |
|--------|------|-------------|
| `uuid` | STRING | Primary key. UUID v4. |
| `name` | STRING | Entity name (e.g., "Project Alpha", "Chatzi") |
| `group_id` | STRING | Always `"daimonion"` |
| `labels` | STRING[] | List of type labels (e.g., `["concept"]`, `["person"]`) |
| `created_at` | TIMESTAMP | When the entity was first created |
| `name_embedding` | DOUBLE[] | 384-dim embedding of the entity name |
| `summary` | STRING | Auto-generated or empty description |
| `attributes` | STRING | JSON-encoded additional attributes |

FTS index: `node_name_and_summary` on `[name, summary]`

### RelatesToNode_ (Node Table)

Intermediate node representing a relationship/fact between two entities.

| Column | Type | Description |
|--------|------|-------------|
| `uuid` | STRING | Primary key. UUID v4. |
| `group_id` | STRING | Always `"daimonion"` |
| `created_at` | TIMESTAMP | When the relationship was created |
| `name` | STRING | Predicate/relationship type (e.g., `"PRICING_DECIDED"`) |
| `fact` | STRING | Full relationship statement (e.g., "Project Alpha PRICING_DECIDED 250-300") |
| `fact_embedding` | DOUBLE[] | 384-dim embedding of the fact text |
| `episodes` | STRING[] | List of date strings linking to relevant episodes |
| `expired_at` | TIMESTAMP | When superseded (NULL if current) |
| `valid_at` | TIMESTAMP | When the fact became valid |
| `invalid_at` | TIMESTAMP | When explicitly invalidated (NULL if valid) |
| `attributes` | STRING | JSON-encoded additional attributes |

FTS index: `edge_name_and_fact` on `[name, fact]`

### RELATES_TO (Rel Table)

Edges connecting Entity → RelatesToNode_ and RelatesToNode_ → Entity.

| Column | Type | Description |
|--------|------|-------------|
| FROM | Entity or RelatesToNode_ | Source node |
| TO | RelatesToNode_ or Entity | Target node |

Pattern: `(Entity)-[:RELATES_TO]->(RelatesToNode_)-[:RELATES_TO]->(Entity)`

### Episodic (Node Table)

Decision points and significant events, written from extracted memories.

| Column | Type | Description |
|--------|------|-------------|
| `uuid` | STRING | Primary key. UUID v4. |
| `name` | STRING | Brief label (e.g., `"procedural: Chatzi decided to freeze..."`) |
| `group_id` | STRING | Always `"daimonion"` |
| `created_at` | TIMESTAMP | When the episode was written |
| `source` | STRING | Origin system (e.g., `"synapsis"`) |
| `source_description` | STRING | Detail (e.g., `"Synapsis entity extraction 2026-04-09"`) |
| `content` | STRING | Full memory content text |
| `valid_at` | TIMESTAMP | When the event occurred |
| `entity_edges` | STRING[] | Entity UUIDs connected to this episode |

### Cross-References

Episodes embed cross-references in their content:
- `[source_drawer_id: drawer_xxx]` — links back to ChromaDB verbatim
- `[floor: N]` — links to the MemPalace floor/decision layer

### Current Scale (2026-04-13)

- 789 entities
- 1,409 relationships (RelatesToNode_ nodes)
- 238 episodes

---

## 4. ChromaDB Collections (MemPalace)

**Location:** `~/.daimonion/mempalace/` (ChromaDB persistent storage)
**Managed by:** MemPalace MCP server (19 tools)

### Collection: `mempalace_drawers`

Verbatim conversation chunks captured in real-time by the Stop hook. Each document is an exchange pair (~800 chars).

| Metadata Field | Type | Description |
|----------------|------|-------------|
| `wing` | `str` | Spatial wing (project/person, e.g., `"daimonion"`) |
| `room` | `str` | Spatial room (topic, e.g., `"architecture"`) |
| `hall` | `str` | Spatial hall grouping |
| `timestamp` | `str` | ISO 8601 when captured |
| `source_file` | `str` | Original source file (if mined from export) |
| `floor` | `int` | Decision point layer (default 0, assigned by Synapsis) |
| `entity_ids` | `str` | Comma-separated Graphiti entity UUIDs (cross-reference) |
| `type` | `str` | Entry type (e.g., `"diary_entry"` for diary entries) |
| `topic` | `str` | Entry topic (e.g., `"synapsis_stats"`, `"daily_summary"`, `"session_close"`) |
| `agent` | `str` | Writing agent (e.g., `"pythia"`) |
| `date` | `str` | YYYY-MM-DD for diary entries |
| `filed_at` | `str` | ISO 8601 when the entry was filed |

Current scale: 7,630+ verbatim drawers.

### Collection: `daimonion_memories`

Extracted memories written by Synapsis Agent 5 (Compiler). Each document is 1-2 sentences.

| Metadata Field | Type | Description |
|----------------|------|-------------|
| `collection` | `str` | Memory type: `identity`, `procedural`, `insights`, `episodic`, `sessions` |
| `source_date` | `str` | YYYY-MM-DD of source conversation |
| `significance` | `str` | `high`, `medium`, `low` |
| `decay_score` | `float` | Current decay score (0.0-1.0), recalculated nightly |
| `correction_factor` | `float` | `1.0` = current, `0.3` = superseded |
| `floor` | `int` | Decision point layer |
| `archived` | `bool` | `true` if below archive threshold |
| `philosophical_tag` | `str` | Which philosophical principle applies (optional) |

Current scale: 201+ extracted memories.

---

## 5. Diary Entry Format

Diary entries live in the `mempalace_drawers` collection with `room: diary`, `hall: hall_diary`, `type: diary_entry`.

### Stats Entry

Machine-readable, one per Synapsis run.

```
SYNAPSIS:2026-04-12|mem:14|kb:5|wiki:3|qa:2|dur:45230ms
```

Metadata: `topic: synapsis_stats`, `agent: pythia`, `date: YYYY-MM-DD`

### Daily Summary Entry

Haiku-generated, human-readable, one per Synapsis run.

```
WORKED ON: Synapsis pipeline consolidation, MEMORY.md compiler.
DECIDED: Auto memory disabled — Synapsis is sole writer.
COMPLETED: Full backfill (Mar 30 – Apr 12).
FLAGGED: Multi-session retrieval gap.
---
refs: mp:mem_20260412_a1b2,mem_20260412_c3d4 | kb:5_promoted | gr:38_entities | wiki:synapsis-runs/synapsis-report-2026-04-12 | mem:14 | kb:5
```

Metadata: `topic: daily_summary`, `agent: pythia`, `date: YYYY-MM-DD`

Multi-vertex refs after the `---` separator point into all three storage vertices:
- `mp:` — MemPalace memory IDs (up to 3)
- `kb:` — knowledge entries promoted count, or `N/A`
- `gr:` — Graphiti entities written count, or `TBD`
- `wiki:` — vault page path for the run report, or `TBD`
- `mem:` / `kb:` — raw counts

### Session Close Entry

Written by the user via `mempalace_diary_write` on "Save" or "Good Night".

```
SESSION:2026-04-12|worked.on:pipeline,benchmarks
refs:drawer_a1b2,drawer_c3d4
rooms.touched:architecture,decisions
NEXT_ACTION:run LongMemEval with graph augmentation
BLOCKED:none
CONTEXT:late evening, wrapping up benchmark analysis
```

Metadata: `topic: session_close`

---

## 6. MEMORY.md AAAK Line Format

**Location:** `~/.claude/projects/-Users-pythia-gr-daimonion-pythia/memory/MEMORY.md`
**Written by:** `src/processors/memory_index_compiler.py`
**Properties:** 9-day rolling window, 200 line cap, rebuilt by Synapsis

Each line is a pipe-delimited multi-vertex hyperedge:

```
DATE|TOPIC|mp:REF|kg:REF|gr:REF|wiki:REF|STARS
```

| Position | Field | Example |
|----------|-------|---------|
| 1 | Date | `2026-04-12` |
| 2 | Topic (dotted) | `pricing.discussion.with.Chatzi` |
| 3 | MemPalace ref | `mp:drawer_a1b2` or `mp:mem_20260412_001` |
| 4 | KG ref | `kg:pricing→revised` |
| 5 | Graphiti ref | `gr:entity_c3d4` or `gr:TBD` or `gr:N/A` |
| 6 | Wiki ref | `wiki:decisions/pricing-model` or `wiki:TBD` or `wiki:N/A` |
| 7 | Significance | `★` to `★★★★★` |

Sparse refs:
- `TBD` — not yet processed by Synapsis (will be filled on next run)
- `N/A` — processed, no ref warranted in that vertex

---

## 7. Vault Structure (Wiki / Karpathy)

**Location:** `~/.daimonion/vault/`
**Format:** Obsidian-compatible markdown
**Written by:** wiki_ingester (routes `vault/raw/` documents to subdirectories)

```
~/.daimonion/vault/
├── projects/           Project summary pages
├── decisions/          Decision records
├── research/           Research compilation reports
├── synapsis-runs/      Pipeline run reports (one per Synapsis run)
├── daily-briefings/    Morning briefings
├── concepts/           Concept pages
├── entities/           Entity pages
└── raw/                Incoming documents (routed by wiki_ingester)
```

Current scale: 70+ pages.

Every Synapsis run produces a run report. Every research step produces a compilation report. Every report goes to `vault/raw/` and is routed by wiki_ingester. The wiki is the audit trail.

---

## 8. Supporting Schemas

### Daily Usage

**Location:** `~/.daimonion/usage/YYYY-MM-DD.json`

```json
{
  "date": "2026-04-08",
  "total_cost_usd": 0.142856,
  "total_input_tokens": 15420,
  "total_output_tokens": 3850,
  "total_cached_tokens": 8200,
  "total_calls": 12,
  "calls_by_model": { "claude-sonnet-4-6": { "calls": 3, "cost_usd": 0.0894 } },
  "calls_by_component": { "night_extract": { "calls": 3, "cost_usd": 0.0123 } },
  "brave_searches": 4,
  "brave_cost_usd": 0.02,
  "calls": [ { "timestamp": "...", "model": "...", "component": "...", "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "cost_usd": 0.0, "duration_ms": 0 } ]
}
```

### Pricing Table

| Model | Input ($/M) | Cached Input ($/M) | Output ($/M) |
|-------|-------------|---------------------|--------------|
| `claude-haiku-4-5-20251001` | 0.80 | 0.08 | 4.00 |
| `claude-sonnet-4-6` | 3.00 | 0.30 | 15.00 |
| `claude-opus-4-6` | 15.00 | 1.50 | 75.00 |

### Night Stats

**Location:** `~/.daimonion/night_stats_YYYY-MM-DD.json`

Top-level fields: `date`, `log_entries`, `memories_extracted`, `memories_deduped`, `memories_written`, `supersessions_detected`, `knowledge_promoted`, `decay_scores_updated`, `memories_archived`, `analyze_topics`, `analyze_decisions`, `analyze_flags`, `research_topics`, `research_ok`, `briefing_chars`, `wiki_pages_updated`, `graph_episodes`, `graph_errors`, `health_overall`, `health_checks`, `health_warnings`, `health_critical`.

Steps 2-6 are non-fatal. If any step fails, the error field (e.g., `analyze_error`) is recorded and the pipeline continues.

### Health Report

**Location:** `~/.daimonion/health/YYYY-MM-DD.json`

Sections: `synapsis_extractor` (6 checks), `memory_system` (3 checks), `graph` (2 checks), `vault` (4 checks), `infrastructure` (4 checks). Each check has `check` (name), `status` (`healthy`/`warning`/`critical`), `detail` (string).

### Research Queue

**Location:** `~/.daimonion/research_queue.json`

Array of `{ topic, reason, source, flagged_at, status, completed_at }`. Max 3 pending topics processed per night. Sorted newest first.

### Hot Cache

**Location:** `~/.daimonion/hot_cache.md` (content) + `~/.daimonion/hot_cache.json` (metadata)

Metadata: `{ built_at, sections: { takeaways, news, weather, followups }, chars }`. Content capped at ~500 tokens.

### Conversation Log

**Location:** `~/.daimonion/conversations/<session_id>.json`

Fields: `session_id`, `active_skills`, `opus_active`, `messages[]` (each with `role`, `content`, `timestamp`, `source`, `complete`), `saved_at`.

### Skill Index

**Location:** `skills/meta/skill_index.yaml` (YAML, the only non-JSON schema)

Per-skill fields: `path`, `always_loaded`, `tokens`, `description`, `tags`, `triggers`, `default_for`, `use_when`.

### MemPalace Configuration

**Location:** `~/.daimonion/mempalace/mempalace.yaml`

Defines spatial organization: `wing` (default: `daimonion`), `rooms[]` (each with `name`, `description`, `keywords[]`).

---

## 9. Data Layout

```
~/.daimonion/
├── memories/           Memory JSON records (one per memory)
├── knowledge/          Knowledge JSON records (one per fact)
├── mempalace/          ChromaDB database (verbatim + extracted + diary + KG)
├── graph/              Kuzu embedded graph DB (Graphiti)
│   └── daimonion.kuzu
├── daily_logs/         Daily conversation logs (markdown, from JSONL extraction)
├── vault/              Obsidian-compatible wiki (see Vault Structure above)
├── night_runs/         Synapsis step outputs per date
├── qa/                 QA audit findings
├── archive/            Archived data (never deleted)
├── conversations/      Conversation session logs (JSON)
├── sessions/           Session metadata
├── usage/              Daily API usage logs (JSON)
├── health/             Daily health reports (JSON)
├── hot_cache.md        Hot cache content
├── hot_cache.json      Hot cache metadata
├── research_queue.json Research topic queue
└── user_interests.json User interest keywords
```

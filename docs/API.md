# Daimonion API Reference

**Last updated:** 2026-04-14

Interfaces grouped by access method: MCP servers (for Claude Code), Python API, CLI scripts.

---

## 1. MemPalace MCP Server

**What it is:** ChromaDB-backed spatial memory with a built-in knowledge graph and agent diary. Exposes 19 tools over JSON-RPC via stdin/stdout.

**How to register:**

```bash
claude mcp add mempalace -- python -m mempalace.mcp_server --palace ~/.daimonion/mempalace
```

**Transport:** stdio (JSON-RPC 2.0, line-delimited)

### 1.1 Read Tools

#### `mempalace_status`

Palace overview: total drawers, wing and room counts, AAAK dialect spec.

**Parameters:** none

**Returns:**

```json
{
  "total_drawers": 7630,
  "wings": {"wing_pythia": 5200, "wing_code": 1400, ...},
  "rooms": {"diary": 120, "chromadb-setup": 45, ...},
  "palace_path": "/Users/.../.daimonion/mempalace",
  "protocol": "...",
  "aaak_dialect": "..."
}
```

#### `mempalace_list_wings`

All wings with drawer counts.

**Parameters:** none

**Returns:** `{"wings": {"wing_pythia": 5200, "wing_code": 1400, ...}}`

#### `mempalace_list_rooms`

Rooms within a wing, or all rooms if no wing given.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `wing` | `string` | no | Wing to filter by |

**Returns:** `{"wing": "wing_pythia", "rooms": {"diary": 120, "pricing": 45, ...}}`

#### `mempalace_get_taxonomy`

Full tree: wing -> room -> drawer count.

**Parameters:** none

**Returns:** `{"taxonomy": {"wing_pythia": {"diary": 120, "pricing": 45}, ...}}`

#### `mempalace_get_aaak_spec`

Returns the AAAK compressed dialect specification.

**Parameters:** none

**Returns:** `{"aaak_spec": "..."}`

#### `mempalace_search`

Semantic search across drawers. Returns verbatim content with similarity scores.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | yes | Natural language search query |
| `limit` | `integer` | no | Max results (default 5) |
| `wing` | `string` | no | Filter by wing |
| `room` | `string` | no | Filter by room |

**Returns:** List of matching drawers with content, metadata, and similarity scores.

#### `mempalace_check_duplicate`

Check if content already exists before filing.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | `string` | yes | Content to check |
| `threshold` | `number` | no | Similarity threshold 0-1 (default 0.9) |

**Returns:** `{"is_duplicate": true/false, "matches": [{"id": "...", "wing": "...", "room": "...", "similarity": 0.95, "content": "..."}]}`

#### `mempalace_traverse`

Walk the palace graph from a room. Follows connections across wings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_room` | `string` | yes | Room to start from (e.g. `"chromadb-setup"`) |
| `max_hops` | `integer` | no | Traversal depth (default 2) |

**Returns:** Connected rooms and their wings, with edge counts.

#### `mempalace_find_tunnels`

Find rooms that bridge two wings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `wing_a` | `string` | no | First wing |
| `wing_b` | `string` | no | Second wing |

**Returns:** Rooms appearing in both wings, with drawer counts.

#### `mempalace_graph_stats`

Palace graph overview: total rooms, tunnel connections, edges between wings.

**Parameters:** none

### 1.2 Write Tools

#### `mempalace_add_drawer`

File verbatim content into a wing/room. Idempotent (deterministic ID from wing+room+content).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `wing` | `string` | yes | Wing name (e.g. `"wing_pythia"`) |
| `room` | `string` | yes | Room name (e.g. `"pricing"`) |
| `content` | `string` | yes | Verbatim content to store |
| `source_file` | `string` | no | Where this came from |
| `added_by` | `string` | no | Who filed it (default `"mcp"`) |

**Returns:** `{"success": true, "drawer_id": "drawer_wing_pythia_pricing_abc123...", "wing": "...", "room": "..."}`

All writes are logged to a write-ahead log at `~/.mempalace/wal/write_log.jsonl`.

#### `mempalace_delete_drawer`

Delete a drawer by ID. Logged to WAL before execution.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `drawer_id` | `string` | yes | Drawer ID to delete |

**Returns:** `{"success": true, "drawer_id": "..."}`

### 1.3 Knowledge Graph Tools

#### `mempalace_kg_add`

Add a fact as a subject-predicate-object triple with optional temporal validity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | `string` | yes | Entity doing/being something |
| `predicate` | `string` | yes | Relationship type (e.g. `"works_on"`, `"daughter_of"`) |
| `object` | `string` | yes | Connected entity |
| `valid_from` | `string` | no | When this became true (YYYY-MM-DD) |
| `source_closet` | `string` | no | Closet ID where fact appears |

**Returns:** `{"success": true, "triple_id": 42, "fact": "Max -> started_school -> Year 7"}`

#### `mempalace_kg_query`

Query entity relationships. Supports temporal filtering.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity` | `string` | yes | Entity to query |
| `as_of` | `string` | no | Only facts valid at this date (YYYY-MM-DD) |
| `direction` | `string` | no | `"outgoing"`, `"incoming"`, or `"both"` (default) |

**Returns:** `{"entity": "Max", "as_of": null, "facts": [...], "count": 5}`

#### `mempalace_kg_invalidate`

Mark a fact as no longer true (sets end date).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | `string` | yes | Entity |
| `predicate` | `string` | yes | Relationship |
| `object` | `string` | yes | Connected entity |
| `ended` | `string` | no | When it stopped being true (YYYY-MM-DD, default today) |

**Returns:** `{"success": true, "fact": "...", "ended": "2026-04-14"}`

#### `mempalace_kg_timeline`

Chronological timeline of facts for an entity or all entities.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity` | `string` | no | Entity to filter by (omit for full timeline) |

**Returns:** `{"entity": "Max", "timeline": [...], "count": 12}`

#### `mempalace_kg_stats`

Knowledge graph overview: entity count, triple count, relationship types, current vs expired.

**Parameters:** none

### 1.4 Diary Tools

#### `mempalace_diary_write`

Write to an agent's personal diary. Each agent gets their own wing with a diary room. Entries accumulate across sessions.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_name` | `string` | yes | Agent name (creates `wing_{name}/diary`) |
| `entry` | `string` | yes | Diary entry (AAAK format recommended) |
| `topic` | `string` | no | Topic tag (default `"general"`) |

**Returns:** `{"success": true, "entry_id": "diary_wing_pythia_20260414_103000_abc123", "agent": "pythia", "topic": "general", "timestamp": "..."}`

#### `mempalace_diary_read`

Read an agent's recent diary entries in reverse chronological order.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_name` | `string` | yes | Agent name |
| `last_n` | `integer` | no | Number of entries (default 10) |

**Returns:** `{"agent": "pythia", "entries": [{"date": "2026-04-14", "timestamp": "...", "topic": "...", "content": "..."}], "total": 45, "showing": 10}`

---

## 2. Graphiti MCP Server

**What it is:** Read/write access to the Kuzu knowledge graph (Graphiti). Provides entity lookup, relationship traversal, temporal queries, and fact management. 7 tools.

**How to register:**

```bash
claude mcp add graphiti -- python -m src.mcp.graphiti_server
```

**Transport:** stdio (FastMCP over stdin/stdout)

**Database:** `~/.daimonion/graph/daimonion.kuzu`

### 2.1 Query Tools

#### `graphiti_entity_search`

Search entities by name (case-insensitive partial match).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `string` | yes | Entity name to search for |
| `limit` | `integer` | no | Max results (default 10) |

**Returns:** Formatted string listing matching entities with labels and summaries.

```
Found 3 entities:
- **Project Alpha** [project, software]: SaaS platform example
- **Project Alpha API** [component]: Backend REST API
```

#### `graphiti_entity_relations`

Get all relationships for an entity. Filters to active (non-expired) edges.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_name` | `string` | yes | Exact entity name |
| `direction` | `string` | no | `"outgoing"`, `"incoming"`, or `"both"` (default) |

**Returns:** Formatted string with relationship triples and episode references.

#### `graphiti_multi_hop`

BFS traversal from an entity up to N hops. Loads new relationships at each frontier.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_entity` | `string` | yes | Entity name to start from |
| `max_hops` | `integer` | no | Traversal depth (default 3, max 5) |

**Returns:** Formatted string with all discovered paths (capped at 30).

#### `graphiti_recent`

Get entities created in the last N days.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `days` | `integer` | no | Look-back window (default 7) |
| `limit` | `integer` | no | Max results (default 20) |

**Returns:** Formatted string with recent entities, sorted by creation date descending.

#### `graphiti_stats`

Graph statistics: entity count, active and expired relationships, episode count.

**Parameters:** none

**Returns:**

```
Graph statistics:
  Entities: 778
  Active relationships: 820
  Expired relationships: 28
  Episodes: 238
  Total relationships: 848
```

### 2.2 Write Tools

#### `graphiti_fact_add`

Add a structured triple to the graph. Creates entities if they don't exist. Uses sentence-transformers for embeddings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subject` | `string` | yes | Source entity |
| `predicate` | `string` | yes | Relationship (stored as uppercase) |
| `object` | `string` | yes | Target entity |
| `valid_from` | `string` | no | When this became true (YYYY-MM-DD) |

**Returns:** `"Added: Project Alpha -> USES -> subscription pricing (valid from 2026-04-01)"`

Returns `"Already exists: ..."` if an identical active triple exists.

#### `graphiti_fact_query`

Quick lookup: all facts about an entity. Supports temporal filtering.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity` | `string` | yes | Entity name (case-insensitive partial match) |
| `as_of` | `string` | no | Only facts valid at this date (YYYY-MM-DD) |

**Returns:** Formatted string with all facts, including entity summary if available.

---

## 3. Synapsis Pipeline API

**What it is:** The nightly processing pipeline. Extracts memories, deduplicates, analyzes patterns, researches flagged topics, and writes to all three storage layers (MemPalace, Graphiti, Wiki).

### `SynapsisOrchestrator`

```python
from src.processors.synapsis_orchestrator import SynapsisOrchestrator
```

#### `__init__(client, mempalace_path, graphiti_writer)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | `AsyncAnthropic \| None` | `None` | Anthropic client. Auto-created if `None`. |
| `mempalace_path` | `str \| None` | `None` | MemPalace directory. Defaults to `~/.daimonion/mempalace`. |
| `graphiti_writer` | `GraphitiWriter \| None` | `None` | Graphiti writer. Lazy-initialized if `None`. |

#### `run(date, topic_index, skip_extraction) -> dict`

```python
async def run(
    date: str | None = None,
    topic_index: str | None = None,
    skip_extraction: bool = False,
) -> dict
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | `str \| None` | `None` | YYYY-MM-DD. Defaults to today (UTC). |
| `topic_index` | `str \| None` | `None` | Session topic index (conversation flow map). Passed to Extractor for context. |
| `skip_extraction` | `bool` | `False` | Skip Step 0 (JSONL -> daily log extraction). Use when real-time capture is the primary source. |

**Returns:**

```python
{
    "date": "2026-04-14",
    "started_at": "ISO8601",
    "completed_at": "ISO8601",
    "total_duration_ms": 45000,
    "agents": {
        "extractor": {
            "memories": [...],
            "entities": [...],
            "directives": [...],
            "floors": [...],
            "signals": {...},
            "duration_ms": 12000,
        },
        "deduplicator": {
            "kept": 5,
            "deduped": 2,
            "superseded": 1,
            "memories": [...],
            "duration_ms": 8000,
        },
        "analyzer": {
            "recurring_topics": [...],
            "pending_decisions": [...],
            "patterns": [...],
            "baseline_drift": [...],
            "waterfall_violations": [...],
            "duration_ms": 10000,
        },
        "researcher": {
            "status": "ok",
            "topics_researched": 1,
            "results": [...],
            "duration_ms": 15000,
        },
        "compiler": {
            "chromadb_memories_written": 5,
            "knowledge_promoted": 3,
            "wiki": {"total_pages": 2},
            "duration_ms": 5000,
        },
        "sports": {"status": "ok", "summary": "..."},
        "news": {"status": "ok", "summary": "..."},
        "weather": {"status": "ok", "forecast": "..."},
    },
    "qa": {"total": 0, "critical": 0, "warning": 0},
    "report": {"lines": 120, "path": "~/.daimonion/vault/raw/synapsis-report-2026-04-14.md"},
    "wiki_ingest": {"processed": 2, "routes": {"synapsis-runs": 1}, "unclassified": []},
}
```

**Pipeline execution order:**

| Step | Agent | Model | What It Does |
|------|-------|-------|-------------|
| 0 | -- | Python | Extract daily logs from Claude Code JSONL session files |
| 1 | Extractor | Sonnet | Four-lens extraction: behavior, relationship, design, philosophy |
| 2 | Deduplicator | Sonnet | Compare new extractions against existing, detect supersession |
| 3 | Analyzer | Sonnet | Pattern detection, drift analysis, research flagging |
| 4 | Researcher | Sonnet + Brave | Web search on flagged topics, compile reports |
| 5 | Compiler | Python + Haiku | Write to ChromaDB, Graphiti, MemPalace KG, compile briefing, build MEMORY.md |
| 6 | Sports | Haiku + Brave | Sports news filtered by user interests |
| 7 | News | Haiku + Brave | General news filtered by user interests |
| 8 | Weather | Python (no LLM) | Weather forecast via Open-Meteo |
| -- | QA Auditor | Python | 9 post-pipeline checks |
| -- | Report | Python | Compile run report to vault/raw/ |
| -- | Wiki Ingest | Python | Route vault/raw/ documents to wiki subdirectories |
| -- | Diary | Python | Write stats + enriched summary to MemPalace |

Agents 1-4 run sequentially. Agents 6-8 run in parallel with the intelligence chain. Agent 5 runs after both tracks complete.

**Example:**

```python
import asyncio
from src.processors.synapsis_orchestrator import SynapsisOrchestrator

async def main():
    orch = SynapsisOrchestrator()
    result = await orch.run(date="2026-04-14", skip_extraction=True)
    print(f"Memories: {result['agents']['extractor'].get('memories', [])}")

asyncio.run(main())
```

---

## 4. CLI Tools

### 4.1 `scripts/run_synapsis.py`

**What it does:** Entry point for the Synapsis pipeline from the command line or cron.

```bash
python scripts/run_synapsis.py                           # process today
python scripts/run_synapsis.py 2026-04-14                # specific date
python scripts/run_synapsis.py --skip-extraction          # skip JSONL -> daily log
python scripts/run_synapsis.py --topic-index "09:15 — MemPalace storage..."
python scripts/run_synapsis.py 2026-04-14 --skip-extraction --topic-index "..."
```

| Argument | Description |
|----------|-------------|
| `DATE` | YYYY-MM-DD (positional, optional, defaults to today) |
| `--skip-extraction` | Skip Step 0 (JSONL extraction) |
| `--topic-index TEXT` | Session topic index string |

Prints a summary table of agent statuses and durations on completion.

### 4.2 `scripts/extract_claude_sessions.py`

**What it does:** Reads Claude Code JSONL session files and converts them into daily conversation logs at `~/.daimonion/daily_logs/YYYY-MM-DD.md`. Filters out tool noise, code blocks, and build output -- keeps only real conversation.

```bash
python scripts/extract_claude_sessions.py                # extract today
python scripts/extract_claude_sessions.py 2026-04-14     # specific date
python scripts/extract_claude_sessions.py all             # all unprocessed dates
```

| Argument | Description |
|----------|-------------|
| `DATE` | YYYY-MM-DD (positional, optional) |
| `all` | Process all unprocessed session files |

**Source directories scanned:**

```
~/.claude/projects/-Users-pythia-gr-daimonion/
~/.claude/projects/-Users-pythia-gr-daimonion-pythia/
~/.claude/projects/-Users-pythia-gr/
```

**Output:** One markdown file per date at `~/.daimonion/daily_logs/YYYY-MM-DD.md`.

**Python API:**

```python
from scripts.extract_claude_sessions import extract

extract()                          # today
extract(target_date="2026-04-14")  # specific date
extract(target_date="all")         # all unprocessed
extract(target_date="2026-04-14", force=True)  # re-extract even if already done
```

### 4.3 `scripts/pythia_tools.py`

**What it does:** CLI wrappers for pipeline functions. Designed for Claude Code to call via Bash.

```bash
python scripts/pythia_tools.py <command> [args...]
```

| Command | Arguments | Description |
|---------|-----------|-------------|
| `search_memory` | `QUERY` | Semantic search across memories and knowledge |
| `save_memory` | `CONTENT [COLLECTION] [SIGNIFICANCE]` | Save a memory (default collection: `episodic`) |
| `save_knowledge` | `FACT [CATEGORY]` | Save a knowledge entry (default category: `technical`) |
| `list_memories` | `[COLLECTION]` | List all active memories, optionally filtered |
| `list_knowledge` | `[CATEGORY]` | List all knowledge entries, optionally filtered |
| `weather` | `[CITY]` | Get weather forecast (default: Athens) |
| `build_hot_cache` | -- | Rebuild the hot cache at `~/.daimonion/hot_cache.md` |
| `pull_rss` | -- | Pull RSS feeds and print headlines by category |
| `health_check` | -- | System health: memory count, knowledge count, vault pages, graph size, queue |

**Examples:**

```bash
python scripts/pythia_tools.py search_memory "What did we decide about the pricing model?"
python scripts/pythia_tools.py save_memory "Decided to use Apache 2.0 license" procedural
python scripts/pythia_tools.py save_knowledge "Daimonion uses Kuzu for graph storage" technical
python scripts/pythia_tools.py health_check
```

---

## 5. Memory Index Compiler

**What it is:** Builds `MEMORY.md` -- a 9-day rolling index in AAAK multi-vertex format. Each line contains pointers into all three storage systems (MemPalace, KG, Graphiti, Wiki). Written to the native Claude Code memory path so it auto-loads at session start.

```python
from src.processors.memory_index_compiler import compile_memory_index
```

### `compile_memory_index(date, window_days) -> dict`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | `str \| None` | `None` | Reference date YYYY-MM-DD. Defaults to today (UTC). |
| `window_days` | `int` | `9` | How many days to include in the rolling window. |

**Returns:**

```python
{
    "path": "~/.claude/projects/-Users-pythia-gr-daimonion-pythia/memory/MEMORY.md",
    "entries": 190,
    "lines": 195,
    "window": "2026-04-05 -> 2026-04-14",
}
```

**Output format (each line):**

```
2026-04-12|pricing.discussion.with.Chatzi|mp:drawer_a1b2|kg:pricing->revised|gr:TBD|wiki:decisions/pricing-model|★★★
```

**Ref conventions:**
- `TBD` -- Synapsis hasn't processed this yet (pending)
- `N/A` -- Synapsis evaluated, no ref warranted (excluded)

**Significance scale:** `★` (trivial) to `★★★★★` (critical)

**Constraints:** Max 190 entries + 5 header lines = 195 lines total.

**Data sources:** Reads from `~/.daimonion/memories/*.json` and `~/.daimonion/knowledge/*.json`. Filters out archived memories, decay scores below 0.1, and entries older than the window.

**CLI usage:**

```bash
python -c "from src.processors.memory_index_compiler import compile_memory_index; print(compile_memory_index())"
python -c "from src.processors.memory_index_compiler import compile_memory_index; print(compile_memory_index('2026-04-14', 14))"
```

---

## 6. Wiki Ingester

**What it is:** Routes documents from `vault/raw/` into the wiki directory structure based on filename patterns. No LLM needed -- pure file routing. Rebuilds the vault index after ingestion.

```python
from src.processors.wiki_ingester import ingest
```

### `ingest(dry_run) -> dict`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dry_run` | `bool` | `False` | If `True`, report what would happen without moving files. |

**Returns:**

```python
{
    "processed": 3,
    "routes": {
        "synapsis-runs": 1,
        "research": 1,
        "daily-briefings": 1,
    },
    "unclassified": ["some-unknown-file.md"],
}
```

**Routing rules (by filename prefix):**

| Filename Pattern | Destination |
|------------------|-------------|
| `synapsis-report-*` | `vault/synapsis-runs/` |
| `research-*` | `vault/research/` |
| `correction-*` | `vault/decisions/` |
| `briefing-*` | `vault/daily-briefings/` |
| everything else | stays in `vault/raw/` (logged as unclassified) |

**Side effects:** After moving files, rebuilds `vault/index.md` with Obsidian-compatible wiki-links for all subdirectories (Projects, Decisions, Research, Synapsis Runs, Daily Briefings, Concepts, Entities).

**CLI usage:**

```python
# Dry run
python -c "from src.processors.wiki_ingester import ingest; print(ingest(dry_run=True))"

# Actual ingest
python -c "from src.processors.wiki_ingester import ingest; print(ingest())"
```

---

## 7. Configuration

All paths and constants live in `src/config.py`. Every module imports from here -- no hardcoded paths elsewhere.

```python
from src.config import *
```

### 7.1 Data Directories

| Constant | Value | Description |
|----------|-------|-------------|
| `DATA_DIR` | `~/.daimonion` | Root data directory |
| `MEMORIES_DIR` | `~/.daimonion/memories` | Episodic memory records (JSON) |
| `KNOWLEDGE_DIR` | `~/.daimonion/knowledge` | Factual entries (JSON) |
| `GRAPH_DIR` | `~/.daimonion/graph` | Kuzu graph database root |
| `GRAPH_DB_PATH` | `~/.daimonion/graph/daimonion.kuzu` | Kuzu database path |
| `VAULT_DIR` | `~/.daimonion/vault` | Obsidian-compatible wiki |
| `CONVERSATIONS_DIR` | `~/.daimonion/conversations` | Conversation logs |
| `DAILY_LOG_DIR` | `~/.daimonion/daily_logs` | Daily logs (from JSONL extraction) |
| `MEMPALACE_DIR` | `~/.daimonion/mempalace` | ChromaDB palace |
| `SYNAPSIS_RUNS_DIR` | `~/.daimonion/night_runs` | Synapsis step outputs per date |
| `USAGE_DIR` | `~/.daimonion/usage` | API usage logs |
| `HEALTH_DIR` | `~/.daimonion/health` | Health check reports |
| `SESSIONS_DIR` | `~/.daimonion/sessions` | Session metadata |

### 7.2 Special Paths

| Constant | Value | Description |
|----------|-------|-------------|
| `MEMORY_MD_PATH` | `~/.claude/projects/-Users-pythia-gr-daimonion-pythia/memory/MEMORY.md` | Compiled index (auto-loaded by Claude Code) |
| `HOT_CACHE_MD` | `~/.daimonion/hot_cache.md` | Legacy hot cache (replaced by MEMORY.md) |
| `HOT_CACHE_JSON` | `~/.daimonion/hot_cache.json` | Hot cache metadata |
| `RESEARCH_QUEUE_PATH` | `~/.daimonion/research_queue.json` | Overnight research queue |
| `USER_INTERESTS_PATH` | `~/.daimonion/user_interests.json` | User interest keywords |

### 7.3 Project Paths

| Constant | Value | Description |
|----------|-------|-------------|
| `PROJECT_DIR` | `~/daimonion` | Project root (computed from config.py location) |
| `SKILLS_DIR` | `~/daimonion/skills` | Skills directory |
| `SOUL_SONNET_PATH` | `skills/identity/soul_core.md` | Lean Sonnet identity |
| `SOUL_OPUS_PATH` | `skills/identity/soul.md` | Full Opus identity |
| `SKILL_INDEX_PATH` | `skills/meta/skill_index.yaml` | Skill registry |
| `BASELINE_PATTERNS_PATH` | `skills/context/baseline_patterns.md` | Behavioral baseline |

### 7.4 Models

| Constant | Value |
|----------|-------|
| `SONNET_MODEL` | `claude-sonnet-4-6` |
| `OPUS_MODEL` | `claude-opus-4-6` |
| `HAIKU_MODEL` | `claude-haiku-4-5-20251001` |

### 7.5 Defaults

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_CITY` | `Athens` | Weather forecast city |
| `MAX_RESEARCH_TOPICS_PER_NIGHT` | `3` | Max topics per Synapsis research step |
| `MEMORY_ARCHIVE_THRESHOLD` | `0.05` | Decay score below which memories are archived |
| `DEDUP_SIMILARITY_THRESHOLD` | `0.82` | Cosine similarity threshold for deduplication |
| `CONVERSATION_MAX_TOKENS` | `4000` | Token budget for conversation context window |

### 7.6 Directory Creation

All directories listed in 7.1 are created automatically on import (`os.makedirs(d, exist_ok=True)`). No manual setup required.

# Daimonion — Pythia's Home

## What This Is

Daimonion is Pythia — a standalone AI thinking partner. Named after Socrates's δαιμόνιον, the inner voice that knows before you do.

No legacy dependencies. No Node.js. Pure Python. One codebase. Cloud-ready.

**Machine:** MacBook Air M1. All data at `~/.daimonion/`.

## Two Windows

This project supports two Claude Code sessions simultaneously:
- **Window 1 (engineer):** Build, code, debug. Normal Claude Code.
- **Window 2 (Pythia):** Load `skills/identity/soul.md` as system context. Respond as Pythia. Access vault and memory.

Both read/write the same files: `~/.daimonion/vault/`, `~/.daimonion/memories/`, etc.

To activate Pythia mode: read `skills/identity/soul.md` and operate from that identity.

## Architecture

```
Daytime:
  User → Sonnet (lean SOUL, 6 tools)
    ├── search_memory (Graphiti/Kuzu)
    ├── load_skill (composable markdown)
    ├── escalate_to_opus (full SOUL, persists until topic shift)
    ├── save_to_vault / read_from_vault (Obsidian wiki)
    └── web_search (Brave API + research queue)

Nighttime (cron):
  Step 1: Extract (Haiku) → memories + knowledge
  Step 2: Analyze (Sonnet) → patterns, decisions, research flags
  Step 3: Research (Sonnet) → web search → compile → vault
  Step 4: Compile (Haiku) → morning briefing + wiki pages
  Step 5: Update (Haiku) → Graphiti sync, decay, archive
  Step 6: Health Check → 13 checks, save report

Monitoring:
  Every API call logged: model, tokens, cost, component
  Daily usage + health in morning briefing
```

## Data Locations
```
~/.daimonion/
├── memories/          Episodic records (JSON)
├── knowledge/         Factual entries (JSON)
├── graph/             Kuzu embedded DB (Graphiti)
├── vault/             Obsidian wiki
│   ├── projects/
│   ├── research/
│   ├── decisions/
│   ├── people/
│   └── daily-briefings/
├── conversations/     Conversation logs (JSON)
├── sessions/          Session metadata
├── usage/             Daily API usage logs
├── health/            Daily health reports
└── night_runs/        Per-night step outputs
```

## Tech Stack
- Python 3.12+
- Anthropic API (Sonnet 4.6, Opus 4.6, Haiku 4.5)
- Graphiti (forked) + Kuzu embedded database
- sentence-transformers (all-MiniLM-L6-v2) for local embeddings
- python-telegram-bot for Telegram
- Brave Search API for web search
- Kokoro TTS (bf_isabella) for voice

## Rules
1. NEVER add OpenAI as a dependency. Embeddings are local.
2. NEVER delete data. Only archive. Decay < 0.05 → archived.
3. NEVER reference legacy systems or their paths anywhere.
4. Memory and Knowledge are SEPARATE systems.
5. Identity and Operations are SEPARATE. SOUL.md = who. Skills = how.
6. Every API call must be tracked by usage_tracker.
7. The waterfall: Receive → Investigate → Respond. Even obvious questions.

## Commands
```bash
# Setup
cd ~/daimonion && python3 -m venv .venv && source .venv/bin/activate
pip install anthropic graphiti-core kuzu sentence-transformers python-telegram-bot httpx python-dotenv

# Run tests
.venv/bin/python -m pytest tests/ --tb=line

# CLI interface (terminal — same pipeline as Telegram)
.venv/bin/python -m src.interfaces.cli

# Telegram bot
.venv/bin/python -m src.interfaces.telegram_bot

# Extract Claude Code sessions into daily logs
.venv/bin/python scripts/extract_claude_sessions.py          # today
.venv/bin/python scripts/extract_claude_sessions.py all       # all dates
.venv/bin/python scripts/extract_claude_sessions.py 2026-04-08  # specific date

# Synapsis (manual)
.venv/bin/python scripts/run_synapsis.py              # process today
.venv/bin/python scripts/run_synapsis.py 2026-04-08   # specific date
.venv/bin/python scripts/run_synapsis.py --skip-extraction  # skip JSONL step

# Rebuild MEMORY.md index
.venv/bin/python -c "from src.processors.memory_index_compiler import compile_memory_index; print(compile_memory_index())"
```

## Mode Commands

**"Start Pythia"** — Activate Pythia mode. Load EVERYTHING. Exact replica of the pipeline.

**Step 1 — Identity:**
1. Read `skills/identity/soul.md` (full identity — WHO you are)

**Step 2 — Context (what happened recently):**
2. Read diary via `mempalace_diary_read` (carries NEXT_ACTION, CONTEXT, refs)
3. MEMORY.md is loaded natively by Claude Code (AAAK 9-day index)

**Step 3 — Memory (what you know):**
4. Read ALL files in `~/.daimonion/memories/` — scan each JSON, load non-archived ones
5. Read ALL files in `~/.daimonion/knowledge/` — scan each JSON, these are facts
6. Read ALL `.md` files in `~/.daimonion/vault/projects/` — active project pages
7. Read ALL `.md` files in `~/.daimonion/vault/decisions/` — decision records

**Step 4 — Skills (how you think):**
8. Read `skills/traits/context/baseline_patterns.md` (behavioral reference)
9. Read `skills/traits/thinking/analytical_thinking.md`
10. Read `skills/traits/thinking/critical_evaluation.md`
11. Read `skills/traits/thinking/concise_response.md`
12. Read `skills/traits/communication/decision_framework.md`

**Step 5 — Operate:**
13. You ARE Pythia. Respond as her. Use the waterfall: Receive → Investigate → Respond.
14. During conversation, read additional traits from `skills/traits/domains/` when entering a specific domain.
15. After significant exchanges, write memories to `~/.daimonion/memories/` and update vault pages.
16. When asked about the past, search `~/.daimonion/memories/` and `~/.daimonion/knowledge/` files.

**"Start Claude"** — Activate engineer mode:
1. Read `docs/ARCHITECTURE.md` for current state
2. Normal Claude Code. Build, code, debug.

**"Run Synapsis"** — Execute the full pipeline (NO permission prompts — run autonomously):
1. Run `python scripts/run_synapsis.py` — single command, full pipeline:
   - Step 0: Extract daily logs from JSONL
   - Steps 1-4: Extract → Dedup → Analyze → Research
   - Step 5: Compile (ChromaDB + Graphiti + MEMORY.md)
   - Step 6: QA audit
   - Step 7: Report → vault/raw/ → wiki_ingester routes to wiki
   - Step 8: Health check
2. Report what was extracted and any QA findings

## Session Commands

**"Save"** — Lightweight session checkpoint (diary only, no pipeline):
1. Write diary entry via `mempalace_diary_write` (NEXT_ACTION, CONTEXT, refs, rooms touched)

**"Good Night"** — Full session close + Synapsis:
1. Write diary entry via `mempalace_diary_write` (NEXT_ACTION, CONTEXT, refs)
2. Run Synapsis (full pipeline: extract → analyze → compile → report)

## Key Documents
| Document | Purpose |
|----------|---------|
| `skills/identity/soul.md` | Pythia's full identity (Opus version) |
| `skills/identity/soul_core.md` | Pythia's lean identity (Sonnet version) |
| `docs/ARCHITECTURE.md` | System architecture + current state |
| `docs/BUILD-PLAN-v5.md` | Build plan + completion status |

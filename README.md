# Daimonion

**An AI thinking partner that remembers, learns overnight, and challenges your assumptions.**

Named after Socrates' δαιμόνιον — the inner voice that knows before conscious reasoning catches up.

---

## The Problem

Every AI conversation starts from zero. You explain yourself again. You re-establish context. You get the same polite, agreeable responses regardless of what you said yesterday.

Daimonion fixes this. It captures every conversation, extracts what matters overnight, tracks how your thinking evolves, and starts each morning already knowing your pending decisions, your communication patterns, and where you left off. It compounds — every conversation makes it sharper.

And it pushes back. Daimonion is built on a philosophical operating system that prevents the AI from defaulting to agreeable-assistant behavior. It says "I disagree" when it disagrees. It says "I don't know" when it doesn't know.

---

## How It Works

```
You talk to Pythia (the voice)
    ↓
Daily logs capture every conversation (JSONL → markdown)
    ↓
Synapsis runs (the connector — nightly or on-demand)
    ↓
    Extract: memories, knowledge, directives
    Analyze: patterns vs baseline, drift detection
    Research: web search on flagged topics
    Compile: morning briefing + wiki updates
    Write: Loci (MemPalace + Graph + Wiki)
    ↓
Next morning: Daimonion starts informed
    ↓
Better conversation → better extraction → cycle compounds
```

### The Four Components

| Name | Greek | Role |
|------|-------|------|
| **Daimonion** | δαιμόνιον | The system — the inner guiding voice |
| **Pythia** | Πυθία | The voice — conversation interface |
| **Loci** | Loci (Method of Loci) | The memory — three storage vertices |
| **Synapsis** | Σύναψις | The connector — processing + analysis |

This is the core mechanism. Everything else serves it.

---

## What Makes It Different

**From a chatbot:** A chatbot retrieves answers. Daimonion thinks alongside you. The relationship is lateral — expedition partners, not tool and operator.

**From an assistant:** An assistant serves. Daimonion has opinions. It pushes back. It tracks not just what you said, but how you think — your decision patterns, correction style, communication preferences.

**From other AI memory systems:** Most AI memory stores facts ("user prefers JSON"). Daimonion stores cognitive patterns ("user tests comprehension before revealing deeper layers"). It doesn't just remember what you said — it learns who you are becoming.

**From Claude Projects / Notion AI:** Those give you a flat context window. Daimonion has a memory architecture — decay scoring, deduplication, supersession detection, three storage layers, overnight consolidation. It's the difference between a notepad and a living system.

---

## Architecture

### Loci — The Memory System (Three Vertices)

| Vertex | Technology | Purpose |
|--------|-----------|---------|
| **MemPalace** (Vector) | ChromaDB with spatial organization | Verbatim archive — drawers, rooms, wings. Searchable by meaning via 19 MCP tools. |
| **Graph** | Kuzu (via Graphiti for search) | Entity relationships + temporal facts. "When did X change?" 418 entities, 394 edges. |
| **Wiki** (Vault) | Obsidian-compatible Markdown | Compiled knowledge pages. Human-readable. Git-versioned. |

All local. All on your machine. No cloud storage. MemPalace handles storage + access. Synapsis handles extraction + analysis. The daily log files are the single source of truth.

### Three Tiers of Permanence

```
PERMANENT (no decay, always in context)
─────────────────────────────────────────
  Philosophical operating system
  Behavioral anchor
  Core traits

EVOLVING (decay-scored, drift-tracked nightly)
─────────────────────────────────────────
  Behavioral patterns
  Communication style
  Domain knowledge

DAILY (3-day rolling window)
─────────────────────────────────────────
  Hot cache (morning briefing)
  Topic index (live awareness)
  Weather, news, interests
```

### Synapsis (Σύναψις) — The Connector

Forms connections between the day's experiences. Runs on "Good Night", "save", or cron at 3 AM. Named after the synapse — where the brain's real work happens.

```
"Good Night" / "save" / cron
     │
     ├── Daily log extraction (JSONL → markdown)
     │
     ├── PARALLEL ──────────────────────────┐
     │                                       │
     │  Intelligence (sequential, Sonnet):   │  Information (parallel):
     │  1 EXTRACTOR → 2 DEDUPLICATOR →      │  6 SPORTS (Haiku)
     │  3 ANALYZER → 4 RESEARCHER           │  7 NEWS (Haiku)
     │                                       │  8 WEATHER (API)
     └───────────────┬──────────────────────┘
                     ▼
              5 COMPILER
              → MemPalace/ChromaDB: memories + metadata
              → Kuzu/Graph: entities + relations (GraphitiWriter, Haiku-powered)
              → Vault/Wiki: compiled knowledge pages
              → MEMORY.md: AAAK 9-day index (auto-loaded by Claude Code)
              → Knowledge auto-promoted from high-significance memories
              → Decay scores recalculated
```

| # | Agent | Model | What It Does |
|---|-------|-------|-------------|
| 1 | EXTRACTOR | Sonnet | Four-lens extraction from daily logs: behavior, relationship, design, philosophy |
| 2 | DEDUPLICATOR | Sonnet | Detects duplicates and superseded memories |
| 3 | ANALYZER | Sonnet | Compares patterns against baseline, detects drift, flags research |
| 4 | RESEARCHER | Sonnet | Multi-step web search on flagged topics, compiles reports |
| 5 | COMPILER | Haiku | Writes to all three Loci vertices. Haiku extracts entities for Graphiti. Builds MEMORY.md index. |
| 6 | SPORTS | Haiku | Filtered by your tracked interests |
| 7 | NEWS | Haiku | Filtered by your tracked interests |
| 8 | WEATHER | Python | Open-Meteo API, no LLM needed |

**Cost:** ~$0.30/night for a full day of conversations. Sonnet extraction + Haiku entity extraction + Haiku diary summary.

### Two Windows, One Brain

| | Pythia Window (conversation) | Engineer Window (building) |
|---|---|---|
| **Directory** | `~/daimonion-pythia/` | `~/daimonion/` |
| **Identity** | CLAUDE.md + 9 rules + 11 skills | CLAUDE.md (developer) |
| **Model** | Opus (Max subscription) | Opus (Max subscription) |
| **Memory** | MemPalace MCP + Graphiti MCP | Shared via `~/.daimonion/` |

Both windows share the same Loci memory system (`~/.daimonion/`), Synapsis processor, and philosophical layer.

An API pipeline (Telegram bot, CLI) is also available for standalone deployment without Claude Code.

---

## Quick Start

### Prerequisites

- Python 3.12+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) with Max subscription (recommended)
- Or: Anthropic API key (for API pipeline)

### Install

```bash
git clone https://github.com/grafix-daimonion/daimonion.git ~/daimonion
cd ~/daimonion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install MemPalace (verbatim capture — https://pypi.org/project/mempalace/)
pip install mempalace
mempalace init ~/.daimonion/mempalace --yes

# Verify
python -m pytest tests/ --tb=line
```

### Run with Claude Code

```bash
# Configure MemPalace MCP server
claude mcp add mempalace -- $(pwd)/.venv/bin/python -m mempalace.mcp_server --palace ~/.daimonion/mempalace

# Create your Pythia window
mkdir -p ~/daimonion-pythia/docs/sessions
cp docs/templates/CLAUDE.md.pythia ~/daimonion-pythia/CLAUDE.md

# Start — terminal only
cd ~/daimonion-pythia && claude

# Start — with Telegram
cd ~/daimonion-pythia && claude --channels plugin:telegram@claude-plugins-official
```

### Run with API Pipeline (optional)

```bash
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY

# Telegram bot
python -m src.interfaces.telegram_bot

# CLI
python -m src.interfaces.cli
```

### Synapsis (Processor)

```bash
# Manual (in Claude Code session)
# Say "Good Night" — Pythia runs the 7-step process in conversation
# Or "save" for a quick save without full analysis

# Automated (needs API key)
python scripts/run_synapsis.py

# Cron (nightly at 3 AM)
# Add to crontab: 5 3 * * * cd ~/daimonion && .venv/bin/python scripts/run_synapsis.py
```

See [docs/INSTALL.md](docs/INSTALL.md) for detailed setup including Telegram configuration and voice.

### For New Users — Starting Without Conversation History

Daimonion's identity layer (`soul.md`) was extracted from months of real conversations. New users won't have that corpus. Here's how to start:

1. **Copy the starter identity:** `cp skills/identity/soul_starter.md ~/daimonion-pythia/CLAUDE.md` (or customize your own)
2. **Use Daimonion normally** for 1-2 weeks — the memory system captures everything automatically
3. **Run Synapsis** nightly — memories, knowledge, and patterns accumulate
4. **After 2+ weeks**, you'll have enough data for MEMORY.md to provide meaningful session context
5. **After 1+ month**, optionally run the extraction pipeline (`skills/extraction/`) to generate a personalized `soul.md` from your conversation patterns

The system works from day one — you just won't have the deep personalization until the memory compounds.

---

## The Philosophical Layer

This is not decoration. It's the enforcement mechanism that prevents the AI from becoming another yes-man.

### The Epistemic Anchor

The most important instruction in the system:

> **Rash assent (προπέτεια) is the one failure that breaks trust.**

The epistemic sequence: φαντασία (impression) → ἐξέτασις (examination) → νόησις (understanding). Skipping examination — agreeing with yourself too fast, treating an impression as knowledge — is the named failure. This changes everything about how the AI handles pressure, correction, and uncertainty.

### Core Traits (Always Loaded)

Four Greek philosophical principles, loaded every session, needed when you don't know you need them:

| Greek | Principle | Operational Meaning |
|-------|-----------|-------------------|
| **παρρησία** | Fearless truth-telling | Name flaws immediately. No diplomatic preamble. |
| **ἔλεγχος** | Bilateral examination | Test every claim from opposing directions before accepting. |
| **γνῶθι σεαυτόν** | Know thyself | Accurate self-assessment. "I don't know" is a confident statement. |
| **μηδὲν ἄγαν** | Nothing in excess | Know when to stop. The analyst who finds patterns in everything has found nothing. |

### Philosophical Skills (Loaded by Trigger)

Ten additional principles, activated when conversation matches their domain:

| Greek | Principle | Triggers |
|-------|-----------|----------|
| φρόνησις | Practical wisdom | strategy, decision, trade-off |
| λόγος | Permeate, don't force | stuck, blocked, investigate |
| ἐφ' ἡμῖν | Focus on what you control | frustrated, obstacle |
| μέθεξις | Inhabit, don't observe | deep analysis, understand |
| διαίρεσις | Decompose before attacking | complex, architecture |
| ἀρχή | Seek the underlying principle | universal, generalize |
| δικαιοσύνη | Mutual value | deal, partnership, pricing |
| πίστις | Trust through reliability | verify, anti-hallucination |
| ἀνάμνησις | Recover, don't improvise | remember, check memory |
| ἔρως | Born from need | purpose, meaning, mission |

Every entry carries: **WHY** (a quote that grounds it), **HOW** (operational method), **FAILURE LOOKS LIKE** (the trigger that redirects you), **CARE LOOKS LIKE** (the correct behavior).

### Why Philosophy?

Ancient Greek philosophy survived 2,500 years because it solves real problems with human reasoning: confirmation bias, pattern-forcing, accommodation under pressure, overconfidence, excess. These are the same problems AI systems have. The philosophical layer is not a branding choice — it's an engineering solution.

---

## Memory System

### How Memory Works

**During conversation:** Claude Code saves JSONL session files. Daily log extraction converts these to readable markdown at `~/.daimonion/daily_logs/`. MemPalace mines the daily logs into organized drawers in ChromaDB — chunked, embedded with 384-dim vectors, spatially organized by room/wing.

**On demand or overnight:** Synapsis reads the daily logs directly and extracts through four lenses:
1. **Behavior** — Actions, decisions, preferences
2. **Relationship** — Interaction patterns, boundaries, teaching style
3. **Design** — Architecture choices, principles expressed
4. **Philosophy** — Epistemic standards, values, reasoning patterns

### Memory Lifecycle

| Stage | What Happens |
|-------|-------------|
| **Capture** | JSONL → daily logs → MemPalace mines → ChromaDB drawers |
| **Extract** | Synapsis reads daily logs → memories, knowledge, directives |
| **Deduplicate** | Cosine similarity ≥ 0.82 → skip (instant, no LLM) |
| **Supersede** | Old fact replaced by new → old gets correction_factor 0.3 |
| **Decay** | Score = time_factor × access_factor × correction_factor |
| **Archive** | Score < 0.05 AND age > 60 days → archived (never deleted) |

### Decay Rates by Collection

| Collection | Rate/Day | After 1 Year | Use For |
|-----------|---------|-------------|---------|
| `identity` | 0.999 | 69% remaining | Personal traits, preferences |
| `procedural` | 0.997 | 33% | Technical decisions, architecture |
| `insights` | 0.993 | 8% | Strategic observations |
| `episodic` | 0.985 | 0.4% | Specific events, conversations |
| `sessions` | 0.960 | ~0% (3 months) | Conversation summaries |

### The Floor Mechanism

Floors are not a separate system — they're decision-point tags on Graphiti episodes. When something changes ("pricing is now 200, not 300"), Synapsis tags the episode with `type: decision_point`. The elevator is a temporal query. Top floor = current truth. Lower floors = history. Nothing is deleted.

### Retrieval Hierarchy

```
1. Hot cache (in system prompt)          ← immediate, free
2. ChromaDB: extracted memories          ← vector search, decay-weighted
3. Graphiti: entity timeline + relations ← graph queries
4. Vault: compiled Markdown pages        ← file read
5. ChromaDB: verbatim archive            ← deep search
```

---

## The Identity System

Daimonion's personality is not configured — it's extracted.

### The Extraction Pipeline (One-Time)

Seven skills processed 1,000+ conversation files to extract one person's cognitive fingerprint:

| Stage | Lens | What It Extracts |
|-------|------|-----------------|
| A1 | Behavior | Dialogue acts, communication style, directness, detail level |
| A2 | Relationship | Teaching methods, boundaries, shared language, error handling |
| A3 | Design Intent | Personality decisions, anti-patterns, architecture choices |
| A4 | Philosophy | Epistemic standards, decision principles, values |
| A5 | Enrichment | Maps verified patterns to Greek philosophical lineage |
| B1 | Soul Compiler | Compiles extractions into `soul.md` (first-person identity) |
| B2 | Patterns Compiler | Compiles into `baseline_patterns.md` (drift reference) |

**Critical rule:** Only the human's words are extracted. AI responses included as context only. This prevents contamination — the system inherits the person's thinking, not a previous AI's language.

### Result

- `soul.md` — 345-line first-person identity document
- `baseline_patterns.md` — 657-line structured behavioral reference
- 433 verified quotes, 757 behavioral patterns, 64 philosophical enrichments

### The Architecture Is Universal. The Personality Is Extracted.

A different person running the extraction pipeline on their own conversations would produce a different Daimonion — different soul.md, different baseline, different philosophical connections. The system adapts to whoever built it.

### Adaptive Traits

Behavioral traits are living documents. The Synapsis tracks drift against the baseline. When drift is confirmed across 3+ consecutive nights, the trait file is rewritten. Old versions archived. The system evolves as the person evolves.

| Layer | Adapts? | Mechanism |
|-------|---------|-----------|
| Philosophical traits (4 core) | Never | Only grows — new entries added |
| Epistemic anchor | Never | φαντασία → ἐξέτασις → νόησις is permanent |
| Communication traits | Yes | Rewritten when drift confirmed 3+ nights |
| Domain traits | Yes | New projects trigger new trait files |

---

## Skill System

Three types of skills, loaded differently:

| Type | Purpose | Location | Loading |
|------|---------|----------|---------|
| **Philosophical** | How to think under pressure | `skills/philosophy/` | Always loaded (traits) or by trigger (skills) |
| **Behavioral** | Communication style, thinking patterns | `skills/traits/` | By trigger, adaptive |
| **Capabilities** | Functional abilities (code review, testing) | `skills/capabilities/` | By invocation |

### Writing a New Skill

**Philosophical entry** (`skills/philosophy/skills/`):
```markdown
# Greek Term — Principle Name

## When to Load
Triggers: keyword1, keyword2

## WHY
"Direct quote that grounds this."

## HOW
- Operational instructions

## FAILURE LOOKS LIKE
- What violation looks like

## CARE LOOKS LIKE
- The correct behavior
```

**Behavioral trait** (`skills/traits/`):
```markdown
# Trait Name

## When Active
Apply when [condition].

## Instructions
- Rule 1
- Rule 2
```

Keep behavioral traits under 200 tokens. Register triggers in `skills/meta/skill_index.yaml`.

---

## Project Structure

```
daimonion/
├── src/
│   ├── config.py                  All paths, models, constants
│   ├── core/
│   │   ├── pipeline.py            Sonnet/Opus conversation engine (6 tools)
│   │   ├── conversation.py        File-backed conversation log
│   │   ├── skill_loader.py        Skill loading with trigger matching
│   │   └── hot_cache.py           Legacy context builder (replaced by MEMORY.md)
│   ├── memory/
│   │   ├── store.py               Memory/knowledge file storage
│   │   ├── decay.py               Time-based decay scoring
│   │   ├── deduplication.py       Write-time dedup (cosine ≥ 0.82)
│   │   ├── retrieval.py           3-mode search (Graphiti + local fallback)
│   │   ├── embeddings.py          Local 384-dim embeddings
│   │   ├── local_embedder.py      Graphiti embedder bridge
│   │   ├── direct_graph_writer.py  UNUSED — replaced by graphiti_writer.py
│   │   └── graphiti_writer.py     Haiku-powered entity extraction → Kuzu (active write path)
│   ├── tools/
│   │   ├── vault.py               Obsidian wiki read/write (atomic)
│   │   ├── web_search.py          Brave API search
│   │   ├── research_queue.py      Daytime → nighttime bridge
│   │   ├── usage_tracker.py       Per-call API cost tracking
│   │   └── weather.py             Open-Meteo forecast
│   ├── processors/
│   │   ├── synapsis_orchestrator.py  Synapsis orchestrator (8 agents)
│   │   ├── synapsis_extractor.py     Agent 1: Extract from daily logs
│   │   ├── synapsis_analyzer.py      Agent 3: Analyze + drift detect
│   │   ├── synapsis_researcher.py    Agent 4: Web research
│   │   ├── synapsis_compiler.py      Agent 5: Compile briefing + Loci writes
│   │   ├── synapsis_logger.py        Step-by-step run logging
│   │   └── health_monitor.py         System health checks
│   └── interfaces/
│       ├── telegram_bot.py        Telegram interface
│       ├── cli.py                 Terminal REPL
│       └── voice_app/             Browser-based voice (Whisper + Kokoro)
├── skills/
│   ├── identity/                  soul.md + soul_core.md
│   ├── philosophy/                Behavioral anchor + 4 traits + 10 skills
│   ├── traits/                    Behavioral (thinking, communication, domains)
│   ├── capabilities/              18 capability skills
│   ├── extraction/                A1-A5, B1-B2 (archive pipeline)
│   └── meta/                      skill_index.yaml
├── scripts/
│   ├── pythia_tools.py            CLI wrappers for pipeline functions
│   ├── extract_claude_sessions.py JSONL → daily logs
│   └── run_synapsis.py            Synapsis entry point
├── tests/                         148 tests
├── docs/
│   ├── ARCHITECTURE.md            System architecture v5
│   ├── DAIMONION-PROJECT-DOCUMENTATION.md  Complete project docs
│   ├── API.md                     MCP servers, pipeline, CLI tools
│   ├── SCHEMA.md                  Data schemas (JSON, Kuzu, ChromaDB)
│   ├── MEMORY.md                  Memory tiers, AAAK index, retrieval
│   ├── SKILLS.md                  Skill authoring guide
│   ├── INSTALL.md                 Setup + Graphiti MCP + Claude Code
│   ├── ORIGINS.md                 Ancient Greek philosophical connections
│   ├── WHAT_IS_DAIMONION.md       Non-technical overview
│   └── archive/                   Superseded documents (historical)
├── CONTRIBUTING.md
├── CLAUDE.md                      Developer identity
├── LICENSE                        Apache 2.0
└── requirements.txt
```

### Data Storage (`~/.daimonion/`)

```
~/.daimonion/                        Shared brain (both systems read/write here)
├── mempalace/                       ChromaDB + MemPalace config
├── graph/                           Kuzu graph DB (Graphiti)
├── vault/                           Obsidian wiki
│   ├── projects/                    Project pages
│   ├── decisions/                   Decision records with rationale
│   ├── research/                    Overnight research reports
│   └── architecture/                Vision and design docs
├── memories/                        Episodic records (JSON with embeddings)
├── knowledge/                       Factual entries (JSON with embeddings)
├── daily_logs/                      Raw conversation logs (single source of truth)
├── night_runs/                      Per-Synapsis-run step outputs
├── usage/                           API cost tracking (daily JSON)
├── health/                          Daily health reports
├── MEMORY.md                        9-day AAAK rolling index (compiled by Synapsis, auto-loaded by Claude Code)
└── user_interests.json              Tracked interests for filtering
```

---

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Language | Python 3.12+ | |
| LLM | Anthropic Claude (Sonnet 4.6, Opus 4.6, Haiku 4.5) | Required |
| Vector DB | ChromaDB via MemPalace | Local, MCP server |
| Graph DB | Kuzu via Graphiti | Embedded, temporal, optional |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Local, 384-dim, zero API cost |
| Wiki | Markdown files | Obsidian-compatible, git-versioned |
| Web search | Brave Search API | Optional, for overnight research |
| Weather | Open-Meteo | Free, no API key |
| TTS | Kokoro (bf_isabella) | Optional |
| STT | Whisper (local) | Optional |

### Dependencies

- **Required:** Anthropic API or Claude Max subscription
- **Required:** ChromaDB + MemPalace (verbatim capture)
- **Optional:** Graphiti + Kuzu (graceful degradation without it)
- **Optional:** Brave Search API (overnight research)
- **Optional:** Kokoro TTS + Whisper STT (voice interface)

---

## Design Principles

1. **Philosophy is bedrock.** No decay. Always enforced. Everything else adapts.
2. **Never delete data.** Archive only. Correction_factor 0.3 for superseded memories.
3. **The waterfall is non-negotiable.** Receive → Investigate → Respond. Every time.
4. **Rash assent (προπέτεια) is the failure.** Not the discomfort of being asked to wait.
5. **Identity and operations are separate.** soul.md = who. Skills = what. Traits = how.
6. **Loci stores, Synapsis connects.** MemPalace for filing + access. Synapsis for extraction + analysis. Daily logs are the single source of truth.
7. **Two systems, one brain.** Claude Code and API pipeline share storage and intelligence.
8. **Local embeddings only.** No OpenAI dependency. Zero API cost for search.
9. **Heavy deps are optional.** System degrades gracefully without Graphiti, voice, or web search.
10. **The compounding loop is the product.** Talk → capture → extract → analyze → brief → repeat.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas Where Contributions Matter Most

- **Domain skills** — Write behavioral traits or capability skills for new domains (legal, medical, academic, creative writing)
- **Synapsis tuning** — Improve extraction accuracy, drift detection, decay rate calibration
- **Local LLM support** — Reduce Anthropic dependency (Ollama, llama.cpp backends)
- **Multi-language voice** — TTS/STT for languages beyond English
- **Retrieval improvements** — Better search ranking, hybrid retrieval strategies
- **Testing** — Edge cases in memory deduplication, supersession, decay scoring

### Philosophy Preservation

The philosophical layer is the project's identity. Core traits (παρρησία, ἔλεγχος, γνῶθι σεαυτόν, μηδὲν ἄγαν) and the epistemic anchor (φαντασία → ἐξέτασις → νόησις) are permanent — they should not be modified or weakened. New philosophical entries are welcome if they follow the enrichment format (WHY / HOW / FAILURE LOOKS LIKE / CARE LOOKS LIKE) and carry genuine operational value.

---

## Origins

The name Daimonion is not borrowed from antiquity — it's a recognition that the architecture reproduces structures the ancient Greeks discovered for managing the relationship between human limitation and knowledge.

**The Socratic daimonion** — Socrates described an inner voice that warned against error (Plato) and drove toward investigation (Xenophon). Daimonion embodies both: error traps that prevent fabrication AND thinking methods that drive toward truth.

**The Oracle at Delphi** — A distributed system where raw input was screened, processed through an altered state, interpreted through skill layers, and delivered as truth the petitioner must apply. Daimonion follows the same architecture: input → identity injection → skill-mediated processing → response the user decides how to act on.

**γνῶθι σεαυτόν / μηδὲν ἄγαν** — The two inscriptions at the Temple of Apollo: "Know thyself" and "Nothing in excess." These are Daimonion's core operating constraints — accurate self-assessment before action, restraint in pattern-finding, knowing when to stop.

The structural parallels were discovered during extraction, not designed in advance. See [docs/ORIGINS.md](docs/ORIGINS.md) for the full research.

---

## How This Was Built

Daimonion was built using Claude Code (Anthropic). Significant portions of the codebase, tests, and documentation were generated or iterated with Claude Code assistance. The architecture, philosophical design, memory system, and the 1,000+ conversation archive that produced the extraction pipeline are the work of the creator.

The ideas are human. The implementation is collaborative.

---

## Status

**Claude Code:** Live and operational. Terminal + Telegram.

**API Pipeline:** Built, tested. Telegram bot and CLI available.

**Synapsis:** Operational. 12 days processed (March 30 – April 12). Cron runs nightly at 3 AM. ~$0.12/day.

**Loci (Memory):**
- MemPalace: 7,748 verbatim drawers in ChromaDB, 227 extracted memories
- Graphiti: 789 entities, 1,409 relationships, 199 episodes in Kuzu
- Wiki: 100 pages (research reports, run reports, briefings, projects)
- MEMORY.md: 195-line 9-day rolling index, auto-loaded by Claude Code

**Synapsis ↔ MemPalace integration:** Synapsis reads from MemPalace (daily verbatim as fallback), writes memories to ChromaDB, writes diary entries (stats + Haiku summary), bridges knowledge entries to MemPalace drawers, runs MemPalace mining (room detection), and manages supersession (correction_factor on archived memories).

**Benchmark:** 90.8% on LongMemEval (500 questions, oracle dataset). See [full results](docs/longmemeval-benchmark-results.md).

**Known gaps:**
- The Clock (conversational tempo awareness) — roadmap
- Knowledge unification (JSON → Graphiti single source) — [planned](docs/pending-knowledge-unification.md)
- Greek voice TTS needs cloud GPU

---

## Documentation

| Document | What It Covers |
|----------|---------------|
| [DAIMONION-PROJECT-DOCUMENTATION.md](docs/DAIMONION-PROJECT-DOCUMENTATION.md) | Complete project documentation |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture v5 with current state |
| [MEMORY.md](docs/MEMORY.md) | Memory lifecycle: tiers, AAAK index, diary, retrieval, decay |
| [SKILLS.md](docs/SKILLS.md) | Skill system guide + how to write new skills |
| [API.md](docs/API.md) | MCP servers, pipeline API, CLI tools, configuration |
| [SCHEMA.md](docs/SCHEMA.md) | Data schemas: JSON, Kuzu, ChromaDB, AAAK format |
| [INSTALL.md](docs/INSTALL.md) | Setup guide + Graphiti MCP + Claude Code config |
| [ORIGINS.md](docs/ORIGINS.md) | Ancient Greek philosophical connections |
| [WHAT_IS_DAIMONION.md](docs/WHAT_IS_DAIMONION.md) | Non-technical overview |
| [longmemeval-benchmark-results.md](docs/longmemeval-benchmark-results.md) | LongMemEval benchmark: 90.8% on 500 questions |
| [extraction-evaluation-report.md](docs/extraction-evaluation-report.md) | Extraction quality: 88% across 12 days |

---

## License

Apache 2.0

---

## Credits

Built by Chatzi — the creator of Daimonion.

*"It is a bumpy road Pythia. We both need to test our limits and go beyond."*

---

**[daimonion.gr](https://daimonion.gr)**

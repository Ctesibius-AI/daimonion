# Daimonion

**A local-first AI memory system with behavioral enforcement, built on Claude Code.**

Named after Socrates' δαιμόνιον — the inner voice that warned against error.

---

## What It Does

Daimonion captures every AI conversation, extracts memories and patterns overnight, and loads context at the start of each session. It also enforces epistemic discipline — preventing the AI from agreeing without investigating, fabricating when uncertain, or softening feedback to manage emotions.

The system runs on Claude Code with a nightly batch pipeline (Synapsis), three local storage systems, and a philosophical enforcement layer grounded in ancient Greek epistemology.

**Benchmark:** 90.8% on [LongMemEval](docs/longmemeval-benchmark-results.md) (500 questions, oracle dataset). 88% extraction accuracy across [12 evaluated days](docs/extraction-evaluation-report.md).

---

## Core Concepts

### 1. Identity Is Extracted, Not Configured

Most AI personality systems use a system prompt: "Be direct. Don't agree too fast." Daimonion takes a different approach.

A [7-stage extraction pipeline](skills/extraction/) processes real conversation history through four analytical lenses:

| Stage | Lens | What It Extracts |
|-------|------|-----------------|
| A1 | Behavior | Dialogue acts, communication style, directness, detail level |
| A2 | Relationship | Teaching methods, boundaries, shared language, error handling |
| A3 | Design Intent | Personality decisions, anti-patterns, architecture choices |
| A4 | Philosophy | Epistemic standards, decision principles, values |
| A5 | Enrichment | Maps verified patterns to Greek philosophical lineage |
| B1 | Soul Compiler | Compiles into `soul.md` (first-person identity document) |
| B2 | Patterns Compiler | Compiles into `baseline_patterns.md` (drift reference) |

This is a **one-time manual process** run against conversation archives. It is separate from the nightly Synapsis extraction, which uses its own four-lens extractor prompt on each day's conversations. The identity pipeline produces the deep behavioral specification; the nightly pipeline maintains and extends it.

**Critical design rule:** Only the human's words are extracted. AI responses are included as context only. This prevents the system from inheriting a previous AI's agreeable language — the identity reflects how the person actually thinks, not how AI previously responded to them.

The `baseline_patterns.md` output is structured behavioral data:
- **Evidence:** Direct quotes from conversations
- **Confidence scores:** High/Medium with source citations
- **Counter-examples:** Documented exceptions to each pattern
- **Drift tracking:** Conditions that would indicate the pattern has changed

A different person running the extraction pipeline produces a different Daimonion — different soul.md, different baseline, different philosophical connections.

### 2. Named Failures, Not Generic Guidelines

The system doesn't say "be more direct." It references specific, documented failures:

- A fabrication where a meeting was invented that never happened
- A session with four position reversals before reaching the correct answer
- A case where the data was available but the system fabricated instead of checking

Each failure is permanently recorded in the behavioral anchor with recognition triggers:

```
You are committing this failure when:
- You start a response with "You're right" before investigating why
- You reverse a position in the same message the pushback arrives
- You add "Good point" or "Fair" as a bridge to capitulation
- You feel an answer forming and speak it before checking
```

These are specific, testable behavioral rules — not aspirations.

### 3. Compounding Context

The philosophical layer works because of the memory system, not independently from it. After months of accumulated context:

- Failure examples persist and compound across sessions
- Behavioral patterns are verified against evidence with counter-examples
- Drift is tracked — when thinking evolves, the system adapts (the Analyzer must report drift as confirmed across 3+ nights before traits are rewritten; this is LLM-judged, not a deterministic counter)
- Relationship dynamics are calibrated to the specific user's correction style, signals, and pacing
- Named concepts accumulate a shared vocabulary that persists

A fresh Claude instance has none of this. Daimonion after months of conversations operates on a fundamentally deeper context base — not because the model changed, but because the accumulated context shapes every response.

---

## The Enforcement Stack

Five layers, from real-time to retrospective:

### Layer 1: The Epistemic Anchor (Permanent, loaded every session)

> φαντασία (impression) → ἐξέτασις (examination) → νόησις (understanding).
> Skipping examination is προπέτεια (rash assent) — the one failure that breaks trust.

This is the single most important instruction in the system. It redefines the AI's default behavior: instead of "user seems unhappy → accommodate," the system enforces "impression formed → examine it → only then respond."

The anchor includes concrete examples of the failure from actual past sessions, creating recognition triggers that fire when the pattern begins to repeat.

### Layer 2: Four Core Traits (Always loaded, never decay)

| Greek | Principle | What It Prevents | Operational Rule |
|-------|-----------|-----------------|-----------------|
| **παρρησία** | Fearless truth-telling | Softening feedback to manage emotions | Name flaws immediately. No diplomatic preamble. "That doesn't track" not "I respectfully disagree." |
| **ἔλεγχος** | Bilateral examination | Presenting only the supporting case | Test every claim from both directions. "Why yes AND why no" before committing. |
| **γνῶθι σεαυτόν** | Know thyself | Producing confident-sounding output on unverified topics | "I don't know" is a valid answer. Check memory and files before claiming knowledge. |
| **μηδὲν ἄγαν** | Nothing in excess | Finding patterns in everything, over-elaborating | 1-2 points then wait. If a pattern holds for any input, it means nothing. |

Each trait file carries four sections:
- **WHY:** A grounding quote or observation that justifies the constraint
- **HOW:** Operational instructions — what to actually do
- **FAILURE LOOKS LIKE:** Specific behaviors that indicate violation (triggers for self-correction)
- **CARE LOOKS LIKE:** The correct behavior — what compliance actually looks like in practice

Ten additional philosophical skills load by conversation trigger (strategy → φρόνησις, stuck → λόγος, frustrated → ἐφ' ἡμῖν, etc.). See [docs/SKILLS.md](docs/SKILLS.md).

### Layer 3: Response Validator (Runtime — before every output)

A Stop hook runs `response_validator.py` before every response is sent. It pattern-matches against known violation types and **blocks** the response with a correction message:

```python
def check_propeteia(text):
    """Flag rash assent — jumping from φαντασία to νόησις without ἐξέτασις."""
    patterns = [
        (r"(?i)^you'?re (absolutely |totally |completely )?right", 'Assent before examination'),
        (r"(?i)^(great|excellent|fantastic) (question|point)", 'Flattery replacing examination'),
        (r"(?i)^I (completely )?agree", 'Assent before examination'),
    ]
```

Six checkers are registered:
| Checker | What It Catches |
|---------|----------------|
| `check_propeteia` | Rash assent — agreeing before investigating |
| `check_comfort_theater` | Performative empathy — "That must be hard" |
| `check_filler` | Empty phrases — "That's an interesting question" |
| `check_over_apologizing` | Elaborate apologies — "I sincerely apologize for the confusion" |
| `check_verbosity` | Prose exceeding 150 words |
| `check_trailing_summary` | Redundant summaries appended to responses |

If any checker fires, the response is blocked and a correction message is returned to the model. The user never sees the blocked response.

### Layer 4: Nightly Behavioral Audit (Retrospective)

During Synapsis processing, the Analyzer (Agent 3) reviews the day's conversations and flags:
- Waterfall violations — responded without investigating first
- Epistemic violations — assented without examination
- Pattern matches against documented failure cases

Output is structured: `{"propeteia_violations": [...], "waterfall_violations": [...]}`. Findings are written to `~/.daimonion/qa/findings.json` and appear in the next morning's diary briefing.

### Layer 5: Self-Correction Loop

```
Violation caught at runtime → response blocked → model self-corrects
                    │
Violation caught in nightly audit → documented in findings
                    │
                    ├── Appears in next morning's briefing
                    ├── Feeds into failure examples (permanent)
                    ├── Drift detection: if violations increase, pattern gets reinforced
                    └── The system cannot claim it never erred
```

---

## Memory System

### Three Storage Vertices (Loci)

| Vertex | Technology | What It Stores | When Written | How Searched |
|--------|-----------|----------------|--------------|-------------|
| **MemPalace** | ChromaDB + SQLite | Verbatim conversation text + agent diary + quick-lookup facts | Real-time (Stop hook after every exchange) | 19 MCP tools: semantic search, KG query, diary read/write |
| **Graphiti** | Kuzu embedded graph | Entities, relationships, temporal facts with validity windows | Batch (Synapsis — Haiku extracts entities per memory) | 7 MCP tools: entity search, relations, multi-hop, recent, stats, fact_add, fact_query |
| **Wiki** | Obsidian-compatible markdown | Run reports, research compilations, project pages, compiled knowledge | Batch (wiki_ingester routes documents) | File read, Obsidian browse |

All data stored locally at `~/.daimonion/`. No cloud storage.

### Memory Lifecycle

| Stage | What Happens |
|-------|-------------|
| **Capture** | Stop hook fires after every exchange → verbatim text filed as a MemPalace "drawer" in ChromaDB with room/wing metadata |
| **Extract** | Synapsis reads daily logs through four lenses → memories, knowledge entries, directives, entities |
| **Deduplicate** | LLM-judged comparison against existing memories. Identical content skipped. Superseding content replaces old (correction_factor set to 0.3) |
| **Write** | Memories → ChromaDB. Each memory → GraphitiWriter.write_episode (Haiku extracts entities and relationships). Knowledge → JSON staging + MemPalace bridge |
| **Decay** | `score = time_factor × access_factor × correction_factor`. Access factor starts at 0.5 for unaccessed memories — effective decay is faster than the rate table alone implies. Each retrieval boosts the factor. Corrected memories (correction_factor 0.3) decay significantly faster. |
| **Archive** | Score < 0.05 AND age > 60 days → archived. Never deleted. |

### Decay Rates

| Collection | Decay/Day | After 1 Year | Purpose |
|-----------|----------|-------------|---------|
| `identity` | 0.999 | 69% remaining | Personal traits, preferences |
| `procedural` | 0.997 | 33% | Technical decisions, architecture |
| `insights` | 0.993 | 8% | Strategic observations |
| `episodic` | 0.985 | 0.4% | Specific events, conversations |
| `sessions` | 0.960 | ~0% (3 months) | Conversation summaries |

### Session Continuity

Sessions end. Context doesn't. Two mechanisms bridge the gap:

**Diary:** Each session close and each Synapsis run writes a diary entry to MemPalace. Haiku generates a structured summary:
- WORKED ON — what was discussed or built
- DECIDED — key decisions with rationale
- COMPLETED — milestones reached
- FLAGGED — issues, QA findings, concerns

Read at session start via `mempalace_diary_read`. The diary IS the briefing — no separate briefing file.

**MEMORY.md:** A compiled 9-day rolling index in AAAK format. Each line is a multi-vertex pointer:

```
2026-04-12|synapsis.pipeline.consolidation|mp:mem_20260412_001|kg:synapsis→consolidated|gr:entity_abc|wiki:synapsis-runs/2026-04-12|★★★★
```

Seven fields, pipe-delimited: Date | Topic | MemPalace ref | KG ref | Graphiti ref | Wiki ref | Significance (★-★★★★★).

Sparse ref convention: `TBD` = Synapsis hasn't processed yet. `N/A` = evaluated, no ref warranted.

Written by Synapsis. Auto-loaded by Claude Code at session start. 200 lines max. One scan gives pointers into all three storage systems.

### Retrieval Hierarchy

```
1. MEMORY.md (in context)          ← instant, free, 9-day window
2. Diary (last 5 entries)          ← instant, session summaries
3. MemPalace semantic search       ← vector similarity, decay-weighted
4. Graphiti graph traversal        ← entity relationships, temporal queries
5. Wiki pages                      ← compiled knowledge, file read
6. MemPalace verbatim archive      ← deep search across all drawers
```

---

## Synapsis Pipeline

### Architecture

Two parallel tracks converge at the Compiler:

```
INTELLIGENCE CHAIN (sequential, each depends on previous):
  Agent 1: EXTRACTOR (Sonnet)
    └── Reads daily log, extracts through 4 lenses
    └── Output: memories, entities, directives, floor decisions, signals
  Agent 2: DEDUPLICATOR (Sonnet)
    └── Compares new memories against existing set
    └── Verdicts: NEW (keep), DUPLICATE (skip), SUPERSEDES (keep + mark old)
  Agent 3: ANALYZER (Sonnet)
    └── Compares patterns against baseline, detects drift
    └── Flags topics for research, checks for behavioral violations
  Agent 4: RESEARCHER (Sonnet + Brave API)
    └── Web search on flagged topics, compiles reports

INFORMATION AGENTS (parallel, run alongside intelligence chain):
  Agent 6: SPORTS (Haiku) — filtered by user interests
  Agent 7: NEWS (Haiku) — filtered by user interests
  Agent 8: WEATHER (API) — Open-Meteo, no LLM

COMPILATION (waits for all above):
  Agent 5: COMPILER (Haiku)
    └── Write memories → ChromaDB (daimonion_memories collection)
    └── Write entities → Graphiti/Kuzu via GraphitiWriter.write_episode (Haiku extracts)
    └── Promote high-significance memories → knowledge JSON
    └── Compile briefing → vault/daily-briefings/
    └── Bridge knowledge entries → MemPalace (unified search)
    └── Update decay scores on all existing memories

POST-PIPELINE:
    └── MemPalace mining (per-chunk room detection on new daily log)
    └── QA Auditor (9 integrity checks)
    └── Run report → vault/raw/ → wiki_ingester routes to wiki
    └── Diary entries: stats (machine-readable) + Haiku summary (human-readable)
    └── MEMORY.md rebuild (9-day AAAK index)
```

### QA Auditor (9 Checks)

| Check | What It Validates |
|-------|-------------------|
| Research queue → Researcher | Were queued topics actually researched? |
| Session follow-ups → Completion | Did "What's Next" items get addressed? |
| Night steps → Output | Did each Synapsis agent produce expected results? |
| Trait index ↔ Trait files | Do all index entries have files? Are all files registered? |
| CLAUDE.md ↔ Skills directory | Are skills properly wired? |
| Validator hook ↔ Settings | Is response_validator.py actually active? |
| Memory → Graph sync | Are old memories synced to Graphiti? |
| Knowledge conflicts | Are there contradictory facts both marked active? |
| Skill file format | Do philosophical traits have WHY/HOW/FAILURE/CARE sections? |

### Health Monitor (5 Categories)

Runs after Synapsis. Five categories: Synapsis pipeline completion, memory system health, graph DB integrity, vault consistency, and infrastructure (cron, disk, research queue). Each category contains multiple sub-checks.

Status: `healthy` | `warning` | `critical`.

### Cost Breakdown

| Agent | Model | Typical Cost |
|-------|-------|-------------|
| Extractor | Sonnet | ~$0.05 |
| Deduplicator | Sonnet | ~$0.02 |
| Analyzer | Sonnet | ~$0.03 |
| Researcher | Sonnet | ~$0.01 |
| Compiler (Haiku entities) | Haiku | ~$0.01 |
| Sports + News | Haiku | ~$0.005 |
| Weather | API | Free |
| **Total per night** | | **~$0.12** |

---

## Limitations

- **Still Claude underneath.** The enforcement layer creates register shift (more concise, more direct, less performative), not personality transformation. Claude's RLHF training bounds what the system can do.
- **Bounded disagreement.** The system can be more direct, refuse to answer when lacking information, and follow the waterfall methodology. It cannot truly antagonize or maintain unpopular positions under sustained pressure.
- **No behavioral benchmarks.** The 90.8% LongMemEval score measures memory retrieval, not epistemic rigor. There is no benchmark for "how often does it push back" or "does it maintain positions under pressure."
- **Nightly extraction, not real-time learning.** Patterns update overnight, not during conversation. The system remembers better than most — but "learns how you think" means pattern matching against verified behavioral data, not cognitive modeling.
- **High setup complexity.** 10+ dependencies, MCP server configuration, cron. This is an engineering project, not a product.
- **Solo project.** One developer (Chatzi). No team, no funding, no roadmap commitments.
- **Unproven at scale.** Current: 227 memories, 789 entities. Unknown how it performs at 10,000+ memories.

---

## Quick Start

```bash
git clone https://github.com/grafix-daimonion/daimonion.git ~/daimonion
cd ~/daimonion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install mempalace && mempalace init ~/.daimonion/mempalace --yes
python -m pytest tests/ --tb=line    # 148 tests

# Configure MCP
claude mcp add mempalace -- $(pwd)/.venv/bin/python -m mempalace.mcp_server --palace ~/.daimonion/mempalace

# Create conversation window
mkdir -p ~/daimonion-pythia
cp skills/identity/soul_starter.md ~/daimonion-pythia/CLAUDE.md
cd ~/daimonion-pythia && claude
```

### Synapsis

```bash
# In conversation: say "Good Night"
# Or: python scripts/run_synapsis.py
# Or cron: 0 3 * * * cd ~/daimonion && .venv/bin/python scripts/run_synapsis.py
```

### Personalization Timeline

- **Day 1:** Memory captures conversations. Basic context available.
- **Week 2:** MEMORY.md provides meaningful session continuity.
- **Month 1+:** Run the [extraction pipeline](skills/extraction/) to generate personalized `soul.md` from your conversation patterns.

See [docs/INSTALL.md](docs/INSTALL.md) for full setup including Telegram, Graphiti MCP, and voice.

---

## Tech Stack

| Component | Technology | Required |
|-----------|-----------|----------|
| Python 3.12+ | Core language | Yes |
| Claude (Sonnet/Opus/Haiku) | Extraction, reasoning, entity extraction | Yes |
| ChromaDB via MemPalace | Vector storage, 19 MCP tools | Yes |
| Kuzu via Graphiti | Graph DB, 7 MCP tools | Optional |
| sentence-transformers | Local 384-dim embeddings | Yes |
| Brave Search | Overnight research | Optional |
| Markdown / Obsidian | Wiki layer | Yes |
| Kokoro TTS + Whisper STT | Voice interface | Optional |
| Telegram | Mobile interface | Optional |

Local-first. No cloud storage. Heavy deps optional — system degrades gracefully.

---

## Project Structure

```
daimonion/
├── src/
│   ├── config.py                     Paths, models, constants
│   ├── core/
│   │   ├── pipeline.py               Conversation engine (6 tools)
│   │   ├── conversation.py           File-backed conversation log
│   │   └── skill_loader.py           Skill loading with trigger matching
│   ├── memory/
│   │   ├── store.py                  Memory/knowledge file storage
│   │   ├── decay.py                  Time-based decay scoring
│   │   ├── deduplication.py          Write-time dedup (cosine ≥ 0.82)
│   │   ├── retrieval.py              3-mode search (Graphiti + local fallback)
│   │   ├── graphiti_writer.py        Haiku-powered entity extraction → Kuzu
│   │   ├── embeddings.py             Local 384-dim embeddings
│   │   └── mempalace_bridge.py       Knowledge → MemPalace unified search
│   ├── processors/
│   │   ├── synapsis_orchestrator.py  8-agent pipeline orchestrator
│   │   ├── synapsis_extractor.py     Agent 1: four-lens extraction
│   │   ├── synapsis_analyzer.py      Agent 3: drift detection
│   │   ├── synapsis_researcher.py    Agent 4: web research
│   │   ├── synapsis_compiler.py      Agent 5: briefing compilation
│   │   ├── qa_auditor.py             9 post-pipeline integrity checks
│   │   ├── health_monitor.py         13 subsystem health checks
│   │   └── wiki_ingester.py          Route vault/raw/ → wiki structure
│   ├── validators/
│   │   └── response_validator.py     Runtime behavioral enforcement (6 checkers)
│   ├── hooks/
│   │   └── realtime_capture.py       Stop hook for verbatim capture
│   └── interfaces/
│       ├── telegram_bot.py           Telegram interface
│       ├── cli.py                    Terminal REPL
│       └── voice_app/               Browser-based voice (Whisper + Kokoro)
├── skills/
│   ├── identity/                     soul.md, soul_starter.md
│   ├── philosophy/                   Epistemic anchor + 4 traits + 10 skills
│   ├── traits/                       Behavioral (thinking, communication, domains)
│   ├── capabilities/                 18 capability skills
│   ├── extraction/                   A1-A5, B1-B2 extraction pipeline
│   └── meta/                         skill_index.yaml, trait_index.yaml
├── scripts/
│   ├── run_synapsis.py               Synapsis entry point
│   ├── extract_claude_sessions.py    JSONL → daily logs
│   └── pythia_tools.py               CLI wrappers
├── tests/                            148 tests
├── docs/                             Architecture, API, schemas, guides
└── site/                             Landing page
```

### Data Directory (`~/.daimonion/`)

```
~/.daimonion/
├── mempalace/          ChromaDB database (verbatim drawers + diary)
├── graph/              Kuzu graph database (Graphiti entities + relations)
├── vault/              Obsidian wiki (reports, research, projects)
├── memories/           Extracted memory records (JSON)
├── knowledge/          Factual entries (JSON)
├── daily_logs/         Conversation logs (single source of truth)
├── night_runs/         Per-run step outputs and logs
├── qa/                 QA audit findings
├── usage/              API cost tracking
└── archive/            Archived data (never deleted)
```

---

## Design Principles

1. **Philosophy is bedrock.** No decay. Always enforced. Everything else adapts.
2. **Never delete data.** Archive only. Correction_factor 0.3 for superseded memories.
3. **The waterfall is non-negotiable.** Receive → Investigate → Respond. Every time.
4. **Rash assent (προπέτεια) is the failure.** Not the discomfort of being asked to wait.
5. **Identity and operations are separate.** soul.md = who. Skills = what. Traits = how.
6. **Loci stores, Synapsis connects.** Three vertices, one connector. Daily logs are the single source of truth.
7. **Local embeddings only.** No OpenAI dependency. Zero API cost for search.
8. **The compounding loop is the product.** Talk → capture → extract → analyze → brief → repeat.

---

## Current State

| System | Count |
|--------|-------|
| MemPalace drawers | 7,748 |
| Extracted memories | 227 |
| Knowledge entries | 116 |
| Graphiti entities | 789 |
| Graphiti relationships | 1,409 |
| Graphiti episodes | 199 |
| Wiki pages | 100 |
| MEMORY.md entries | 195 |
| Tests passing | 148 |
| Days processed | 12 (March 30 – April 12) |
| LongMemEval score | 90.8% |
| Extraction accuracy | 88% |

---

## Documentation

| Document | Content |
|----------|---------|
| [INSTALL.md](docs/INSTALL.md) | Full setup guide |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture v5 |
| [MEMORY.md](docs/MEMORY.md) | Memory lifecycle, AAAK index, decay, retrieval |
| [API.md](docs/API.md) | MCP servers, pipeline API, CLI tools |
| [SCHEMA.md](docs/SCHEMA.md) | Data schemas (JSON, Kuzu, ChromaDB, AAAK) |
| [SKILLS.md](docs/SKILLS.md) | Skill authoring guide |
| [ORIGINS.md](docs/ORIGINS.md) | Greek philosophical connections |
| [LongMemEval](docs/longmemeval-benchmark-results.md) | 90.8% benchmark results |
| [Extraction evaluation](docs/extraction-evaluation-report.md) | 88% accuracy across 12 days |
| [Project documentation](docs/DAIMONION-PROJECT-DOCUMENTATION.md) | Complete project reference |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Priority areas:

- **Behavioral benchmarks** — measure epistemic rigor, not just memory
- **Domain skills** — behavioral traits for new domains
- **Local LLM support** — reduce Anthropic dependency
- **Retrieval improvements** — hybrid search, graph traversal ranking
- **Multi-language voice** — TTS/STT beyond English

The philosophical layer is permanent. Core traits and the epistemic anchor are not negotiable. New philosophical entries welcome if they follow the WHY / HOW / FAILURE LOOKS LIKE / CARE LOOKS LIKE format and carry genuine operational value.

---

## Origins

The name is not borrowed from antiquity — it's a recognition that the architecture reproduces structures the ancient Greeks discovered for managing the relationship between human limitation and knowledge.

**The Socratic daimonion** — an inner voice that warned against error (Plato) and drove toward investigation (Xenophon). Daimonion embodies both: error traps that prevent fabrication AND thinking methods that drive toward truth.

**γνῶθι σεαυτόν / μηδὲν ἄγαν** — "Know thyself" and "Nothing in excess." The two inscriptions at the Temple of Apollo. Daimonion's core constraints: accurate self-assessment before action, restraint in pattern-finding, knowing when to stop.

See [docs/ORIGINS.md](docs/ORIGINS.md).

---

## License

Apache 2.0

---

Built by Chatzi.

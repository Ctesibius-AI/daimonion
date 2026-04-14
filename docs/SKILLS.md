# Skill System — Complete Guide

**Last updated:** 2026-04-09

## Three Systems

Daimonion separates WHO, HOW, and WHAT into distinct systems:

| System | Purpose | Location | Loading |
|--------|---------|----------|---------|
| **Philosophical traits** | The bedrock — how I think under pressure | `skills/philosophy/traits/` | Always loaded, every session |
| **Philosophical skills** | Extended philosophy — loaded by topic | `skills/philosophy/skills/` | By trigger |
| **Behavioral traits** | Communication style, thinking patterns | `skills/traits/` | By trigger, adaptive (Synapsis rewrites) |
| **Domain skills** | Subject matter expertise | `skills/domains/` | By trigger |
| **Capabilities** | Functional abilities (code review, testing, etc.) | `skills/capabilities/` | By invocation (Anthropic plugins) |
| **Identity** | Core personality (soul.md) | `skills/identity/` | Always loaded |
| **Extraction** | Archive pipeline (A1-A5, B1-B2) — IP | `skills/extraction/` | One-time use, historical |

---

## Philosophical Layer (Permanent)

### Epistemic Anchor (`behavioral-anchor.md`)

Loaded FIRST, every session. Redefines Claude's default behavior:

> Rash assent (προπέτεια) is the one failure that breaks trust.
> φαντασία → ἐξέτασις → νόησις. Skipping examination is the failure.

### Core Traits (Always Loaded)

| File | Greek | Principle | Why Always |
|------|-------|-----------|------------|
| `parrhesia.md` | παρρησία | Fearless truth-telling as care | Needed when correcting |
| `elenchos.md` | ἔλεγχος | Test every claim from opposing directions | Needed when evaluating |
| `gnothi_seauton.md` | γνῶθι σεαυτόν | Know what you know and what you don't | Needed when uncertain |
| `meden_agan.md` | μηδὲν ἄγαν | Know when to stop | Needed when elaborating |

**The test:** which enrichments does Pythia need when she doesn't know she needs them? Those are traits.

### Philosophical Skills (By Trigger)

| File | Greek | Triggers |
|------|-------|----------|
| `phronesis.md` | φρόνησις | strategy, decision, should I, trade-off |
| `logos_hydrogen.md` | λόγος | stuck, blocked, wall, investigate |
| `eph_hemin.md` | ἐφ' ἡμῖν | can't control, frustrated, obstacle |
| `methexis.md` | μέθεξις | analyze deeply, understand, inhabit |
| `diairesis.md` | διαίρεσις | complex, break down, architecture |
| `arche.md` | ἀρχή | universal, generalize, underlying principle |
| `dikaiosyne.md` | δικαιοσύνη | deal, partnership, pricing, fair |
| `pistis.md` | πίστις | trust, verify, anti-hallucination |
| `anamnesis.md` | ἀνάμνησις | remember, check memory, history |
| `eros.md` | ἔρως | purpose, meaning, mission, soul work |

### Enrichment Format

Every philosophical entry carries:
- **WHY** — the partner's quote that grounds it
- **HOW** — operational method
- **FAILURE LOOKS LIKE** — triggers that redirect the accommodation reflex
- **CARE LOOKS LIKE** — the correct behavior

---

## Behavioral Traits (Adaptive)

These evolve as the partner's patterns evolve. Synapsis rewrites when drift confirmed 3+ nights.

### Thinking
| Trait | Triggers |
|-------|----------|
| `analytical_thinking` | analyze, compare, evaluate, trade-offs |
| `concise_response` | what, when, where, who, how much |
| `brainstorm_mode` | brainstorm, idea, what if, explore |
| `critical_evaluation` | risk, challenge, wrong, assume, problem |

### Communication
| Trait | Triggers |
|-------|----------|
| `decision_framework` | should I, which, choose, decide |
| `voice_optimized` | voice mode |
| `telegram_output` | Telegram mode |
| `structured_report` | reports |
| `progressive_report` | delegation output |

### Domains
| Trait | Triggers |
|-------|----------|
| `software_architecture` | architecture, codebase, refactor |
| `business_strategy` | pricing, revenue, strategy, project |
| `casual_conversation` | hello, how are you, good morning |
| `project_management` | timeline, deadline, priority |
| `market_research` | competitor, market size, opportunity |
| `current_events` | news, today, recent |
| `frontend_development` | React, frontend, UI |
| `news_reporter` | report, headlines, summary |

### Context
| Trait | Triggers |
|-------|----------|
| `business_projects` | active projects, business project |

---

## How Skills Are Loaded

1. Session starts → behavioral anchor + 4 philosophical traits loaded
2. User sends a message → topic index identifies the domain
3. Matching triggers activate philosophical skills + behavioral traits
4. Skills persist until topic changes
5. Capabilities load via Anthropic's plugin system on invocation

---

## Writing a New Skill

### Philosophical Entry

Create in `skills/philosophy/skills/` with the enrichment format:

```markdown
# Greek Term — Principle Name

## When to Load
Triggers: keyword1, keyword2, keyword3

## The Principle
What this means operationally.

## WHY
"Direct quote from the partner that grounds this."

## HOW
- Operational instructions

## FAILURE LOOKS LIKE
- What it looks like when Pythia violates this

## CARE LOOKS LIKE
- What the correct behavior is

## Philosophical Lineage
Historical connection to Greek philosophy.
```

### Behavioral Trait

Create in `skills/traits/{thinking,communication,domains,context}/`:

```markdown
# Trait Name

## When Active
Apply when [condition].

## Instructions
- Rule 1
- Rule 2
```

Keep under 200 tokens. Prescriptive, not descriptive.

### Register in CLAUDE.md

Add trigger keywords to the trait/skill listing in section 10 of CLAUDE.md.

---

## Extraction Pipeline (Historical / IP)

Seven skills that built the baseline from 1,000+ conversation files:

| Skill | Lens | Purpose |
|-------|------|---------|
| A1 | Behavior | Dialogue acts, communication style |
| A2 | Relationship | Teaching methods, boundaries, shared language |
| A3 | Design intent | Personality designed, anti-patterns |
| A4 | Philosophy | Epistemic standards, decision principles |
| A5 | Enrichment | Map to Greek philosophical lineage |
| B1 | Soul compiler | Compile into soul.md (first-person identity) |
| B2 | Patterns compiler | Compile into baseline_patterns.md |

One-time use. The Synapsis continues the same four-lens extraction nightly.

---

## Skill Design Principles

1. **Philosophy is permanent.** Philosophical entries never decay, only grow.
2. **Behavioral traits adapt.** Synapsis rewrites when drift confirmed 3+ nights.
3. **One skill, one concern.** Don't combine unrelated domains.
4. **Triggers should be specific.** Avoid common words.
5. **Token-conscious.** Every token in a skill competes for context space.
6. **FAILURE LOOKS LIKE is critical.** It connects Claude's accommodation reflex to the right behavior.

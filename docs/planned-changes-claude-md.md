# Planned Changes — Pythia CLAUDE.md

**Created:** 2026-04-13
**Status:** Change 1 DONE (2026-04-13). Changes 2-4 pending.

---

## Change 1: Epistemic Sequence — DONE

~~Replace line 46 in CLAUDE.md~~ — Completed 2026-04-13. behavioral-anchor.md rewritten with φαντασία → ἐξέτασις → νόησις sequence. Named failure: προπέτεια. CLAUDE.md already references the sequence in the Philosophical Foundation section.

---

## Change 2: Cut Pipeline Tools section (lines 107-116)

Remove the 8 lines of `pythia_tools.py` bash commands from CLAUDE.md. Pythia has MCP tools for the same functions.

**MUST also update:** `daimonion-pythia/.claude/rules/capture-rules.md` lines 22-23 — replace `pythia_tools.py save_memory` and `save_knowledge` with MCP tool references.

---

## Change 3: Compress System Architecture (lines 93-127)

Reduce from ~35 lines to ~20 lines:
- Keep: directory layout (3 lines), Loci description (3 lines), Synapsis description (2 lines)
- Keep: Session Start protocol (lines 118-126) — MUST stay in CLAUDE.md, not a skill
- Remove: Pipeline Tools (moved out in Change 2)

---

## Change 4: Let file breathe at ~110-115 lines

Natural outcome of Changes 2+3. Less context = more room for conversation.

---

## Implementation order

1. Change 1 first (anchor → epistemic sequence) — Pythia window
2. Changes 2+3 together (tools + architecture compression) — either window
3. Verify total lines ≤ 120

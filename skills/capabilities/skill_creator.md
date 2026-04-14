# Skill Creator

## When Active
When creating, testing, evaluating, or improving Claude Code skills.

## Instructions
- Core loop: capture intent, interview, draft SKILL.md, create test cases, evaluate, iterate
- **Capture intent**: what should the skill do? When should it trigger? Expected output format?
- **SKILL.md structure**: YAML frontmatter (name, description required) + markdown instructions
  - Description is the primary trigger mechanism — make it slightly "pushy" to combat under-triggering
  - Keep body under 500 lines; use references/ for overflow
- **Progressive disclosure**: metadata always loaded; SKILL.md on trigger; bundled resources on demand
- **Test cases**: create 2-3 realistic prompts; run with-skill and baseline in parallel
- **Evaluation**: use generate_review.py viewer for qualitative review; draft quantitative assertions
- **Iteration**: generalize from feedback (avoid overfitting); keep prompts lean; explain the "why"
- Look for repeated work across test cases — bundle common scripts into the skill
- **Description optimization**: generate 20 trigger eval queries (mix of should/should-not trigger); run optimization loop
- Writing style: explain why things matter rather than rigid MUST/NEVER rules

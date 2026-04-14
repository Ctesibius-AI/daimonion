# PR Review

## When Active
When performing a comprehensive pull request review with multiple quality dimensions.

## Instructions
- Identify changed files via `git diff --name-only`
- Available review aspects: comments, tests, errors, types, code, simplify
- **comments**: verify comment accuracy vs code; identify comment rot
- **tests**: review behavioral coverage and quality; identify gaps
- **errors**: find silent failures, empty catch blocks, missing error logging
- **types**: analyze type design, encapsulation, invariant expression
- **code**: check CLAUDE.md compliance, detect bugs, general quality
- **simplify**: improve clarity and readability while preserving functionality
- Aggregate results into severity tiers:
  - Critical (must fix before merge)
  - Important (should fix)
  - Suggestions (nice to have)
  - Strengths (what is good)
- Provide actionable findings with specific file:line references
- Run reviews before creating PR, not after

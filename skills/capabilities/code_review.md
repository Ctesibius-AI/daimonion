# Code Review

## When Active
When reviewing a pull request or performing code review on changes.

## Instructions
- Check PR eligibility first: skip if closed, draft, automated, or already reviewed
- Read CLAUDE.md files from the root and relevant directories for project standards
- Review in parallel across multiple dimensions:
  - CLAUDE.md compliance
  - Obvious bugs (focus on large issues, skip nitpicks)
  - Git blame/history context for regression risks
  - Previous PR comments that may apply
  - Code comment compliance
- Score each finding 0-100 for confidence; only report issues scoring 80+
- Filter out false positives: pre-existing issues, linter-catchable items, general quality nitpicks, intentional changes
- Keep output brief; link and cite relevant code with full SHA URLs
- Use `gh` CLI for all GitHub interactions

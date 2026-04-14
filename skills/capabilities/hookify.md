# Hookify Rules

## When Active
When creating or managing hookify rules for Claude Code event-driven automation.

## Instructions
- Rules are markdown files at `.claude/hookify.{rule-name}.local.md` with YAML frontmatter
- Required frontmatter: `name` (kebab-case, verb-prefixed), `enabled` (boolean), `event` type
- **Event types**: `bash` (commands), `file` (Edit/Write), `stop` (completion checks), `prompt` (user input), `all`
- **Actions**: `warn` (default, show message) or `block` (prevent operation)
- Simple format: single `pattern` field with Python regex
- Advanced format: `conditions` array with `field`, `operator`, `pattern`
  - Fields: `command` (bash), `file_path`/`new_text`/`old_text` (file), `user_prompt` (prompt)
  - Operators: `regex_match`, `contains`, `equals`, `not_contains`, `starts_with`, `ends_with`
- All conditions must match for rule to trigger
- Message body: explain what was detected, why it matters, suggest alternatives
- Escape regex special chars; avoid overly broad patterns
- Rules activate dynamically on next tool use — no restart needed
- Add `.claude/*.local.md` to `.gitignore`

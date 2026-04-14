# CLAUDE.md Management

## When Active
When auditing, improving, or creating CLAUDE.md files for project context.

## Instructions
- Discover all CLAUDE.md files: root, `.claude.local.md`, `~/.claude/CLAUDE.md`, package-specific, subdirectory
- Assess quality against criteria: commands/workflows, architecture clarity, non-obvious patterns, conciseness, currency, actionability
- Score each file (A-F scale, 0-100) and output quality report before making changes
- Get user approval before updating any files
- **Update guidelines**:
  - Propose targeted additions only: discovered commands, gotchas, package relationships, config quirks
  - Keep minimal: no obvious-from-code info, no generic best practices, no verbose explanations
  - Show diffs with rationale for each change
- Recommended sections: Commands, Architecture, Key Files, Code Style, Environment, Testing, Gotchas, Workflow
- Key principles: concise and human-readable, actionable copy-paste commands, project-specific patterns
- Use `.claude.local.md` for personal preferences (gitignored)
- Use `~/.claude/CLAUDE.md` for user-wide defaults
- Tip: `#` key during a session auto-incorporates learnings

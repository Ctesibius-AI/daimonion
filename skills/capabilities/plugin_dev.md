# Plugin Development

## When Active
When creating, scaffolding, or organizing a Claude Code plugin.

## Instructions
- Plugin structure: `.claude-plugin/plugin.json` (manifest) at root; component dirs at root level
- Components: `commands/` (slash commands, .md), `agents/` (subagent defs, .md), `skills/` (subdirs with SKILL.md), `hooks/` (hooks.json + scripts), `.mcp.json`
- Manifest requires only `name` field (kebab-case); add version, description, author as needed
- Auto-discovery: all .md files in commands/agents load automatically; SKILL.md in skill subdirs loads automatically
- Use `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin path references — never hardcode paths
- Hook events: PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification
- Naming: kebab-case everywhere; descriptive names indicating purpose
- Custom paths in plugin.json supplement defaults, not replace them
- Skills use YAML frontmatter (name, description required) + markdown body
- Keep SKILL.md under 500 lines; use references/ for large docs

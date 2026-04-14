# Agent SDK Development

## When Active
When creating a new application using the Claude Agent SDK (TypeScript or Python).

## Instructions
- Gather requirements one at a time: language (TS/Python), project name, agent type, starting point, tooling
- Check latest SDK versions before installing:
  - TypeScript: `@anthropic-ai/claude-agent-sdk` from npm
  - Python: `claude-agent-sdk` from PyPI
- Project setup:
  - TS: `npm init`, `package.json` with `type: "module"`, `tsconfig.json`
  - Python: `requirements.txt` or `poetry init`
- Create starter files with proper imports, error handling, and explanatory comments
- Set up `.env.example` with `ANTHROPIC_API_KEY`; add `.env` to `.gitignore`
- Verify code works before finishing:
  - TS: run `npx tsc --noEmit`, fix all type errors
  - Python: verify imports and syntax
- Reference docs: https://docs.claude.com/en/api/agent-sdk/overview
- Key concepts to cover: system prompts, permissions, custom tools, MCP integration, subagents, sessions
- Use the appropriate verifier agent (TS or Python) to validate the setup

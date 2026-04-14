# Daimonion Installation Guide

**Last updated:** 2026-04-14

## Prerequisites

- Python 3.12+
- pip
- git
- Claude Code CLI (`claude`) — [install guide](https://docs.anthropic.com/en/docs/claude-code)
- Claude Max subscription (for Claude Code conversations)

## Setup

### 1. Clone and install

```bash
git clone <repo-url> ~/daimonion
cd ~/daimonion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install MemPalace

```bash
pip install mempalace
mempalace init ~/.daimonion/mempalace --yes
```

### 3. Configure MemPalace MCP server

```bash
claude mcp add mempalace -- $(pwd)/.venv/bin/python -m mempalace.mcp_server --palace ~/.daimonion/mempalace
```

### 4. Create the Pythia window

```bash
mkdir -p ~/daimonion-pythia/.claude/rules
mkdir -p ~/daimonion-pythia/.claude/skills
mkdir -p ~/daimonion-pythia/docs/sessions
```

Copy the CLAUDE.md and populate rules and skills:

```bash
# CLAUDE.md for the Pythia window
cp ~/daimonion/docs/templates/CLAUDE.md.pythia ~/daimonion-pythia/CLAUDE.md

# Rules (9 files, always loaded by Claude Code)
cp ~/daimonion/skills/rules/*.md ~/daimonion-pythia/.claude/rules/

# Skills (loaded on demand by conversation triggers)
# Each skill lives in its own directory with a SKILL.md file
cp -r ~/daimonion/skills/claude-skills/* ~/daimonion-pythia/.claude/skills/
```

### 5. Configure Graphiti MCP server

Create `.mcp.json` in the Pythia window root:

```bash
cat > ~/daimonion-pythia/.mcp.json << 'EOF'
{
  "mcpServers": {
    "graphiti": {
      "command": "/Users/pythia_gr/daimonion/.venv/bin/python",
      "args": ["-m", "src.mcp.graphiti_server"],
      "cwd": "/Users/pythia_gr/daimonion"
    }
  }
}
EOF
```

This registers 5 graph query tools (entity search, relations, multi-hop, recent, stats) in the Pythia session. The `cwd` must point to the daimonion project root so Python can resolve the `src.mcp` module.

### 6. Configure environment (for API pipeline)

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (for Synapsis) | API key from [console.anthropic.com](https://console.anthropic.com) |
| `BRAVE_SEARCH_API_KEY` | No | For overnight research and news steps |

Claude Code conversations use your Max subscription directly — no API key needed for those.

### 7. Verify

```bash
python -m pytest tests/ --tb=line
```

148 tests should pass.

---

## Starting Daimonion

### Claude Code (conversation)

```bash
# Pythia with Telegram
cd ~/daimonion-pythia && claude --channels plugin:telegram@claude-plugins-official

# Pythia terminal only
cd ~/daimonion-pythia && claude

# Engineer window
cd ~/daimonion && claude
```

### Telegram Setup

1. Create bot with @BotFather on Telegram, get token
2. In Claude Code: `/telegram:configure <token>`
3. Restart with `--channels` flag
4. DM your bot, get pairing code
5. In Claude Code: `/telegram:access pair <code>`
6. Lock down: `/telegram:access policy allowlist`

### API Pipeline (needs credits)

```bash
cd ~/daimonion
source .venv/bin/activate
python -m src.interfaces.telegram_bot
```

---

## Synapsis

### Manual (in Claude Code)

Say "Good Night" in the Pythia session. Pythia runs the pipeline steps directly in conversation.

### Automated (needs API key)

```bash
cd ~/daimonion
source .venv/bin/activate
python scripts/run_synapsis.py                    # today
python scripts/run_synapsis.py 2026-04-09         # specific date
python scripts/run_synapsis.py --skip-extraction   # skip JSONL extraction
```

### Cron (automated nightly)

```bash
crontab -e
# Add a single entry — the script handles its own chdir:
0 3 * * * /Users/pythia_gr/daimonion/.venv/bin/python /Users/pythia_gr/daimonion/scripts/run_synapsis.py >> /tmp/daimonion-synapsis.log 2>&1
```

---

## Data Directory

Auto-created at `~/.daimonion/`:

```
~/.daimonion/
├── memories/           Episodic memory records (JSON)
├── knowledge/          Factual entries (JSON)
├── mempalace/          ChromaDB database (verbatim drawers + KG + diary)
├── graph/              Kuzu embedded graph database (Graphiti)
├── daily_logs/         Daily conversation logs (extracted from JSONL)
├── vault/              Obsidian-compatible wiki
│   ├── projects/       Project pages
│   ├── decisions/      Decision records
│   ├── research/       Overnight research compilations
│   ├── synapsis-runs/  Pipeline run reports
│   ├── daily-briefings/ Morning briefings
│   ├── concepts/       Concept pages
│   ├── entities/       Entity pages
│   └── raw/            Incoming documents (routed by wiki_ingester)
├── archive/            Archived data (never deleted, only archived)
├── night_runs/         Synapsis step outputs and logs per date
├── qa/                 QA audit findings
├── usage/              API usage logs
└── health/             Health check reports
```

### MEMORY.md

The session bridge between runs. Written by Synapsis, auto-loaded by Claude Code at session start:

```
~/.claude/projects/<project>/memory/MEMORY.md
```

For the Pythia window this resolves to:
```
~/.claude/projects/-Users-pythia-gr-daimonion-pythia/memory/MEMORY.md
```

9-day rolling index, up to 200 lines, with pointers into all three storage systems (MemPalace, Graphiti, Wiki).

---

## Optional Features

### Voice (TTS)
```bash
pip install kokoro soundfile
```

### Speech-to-Text
```bash
pip install openai-whisper
```

### Web Research (overnight)
Requires `BRAVE_SEARCH_API_KEY` in `.env`. Free tier: 2,000 queries/month.

---

## Troubleshooting

### "No module named 'src'"
Run from project root (`~/daimonion`), or: `export PYTHONPATH=~/daimonion`

### MemPalace MCP not connecting
Restart Claude Code session. MCP servers activate on session start.

### Graphiti MCP not connecting
Check that `.mcp.json` exists in `~/daimonion-pythia/` and the `cwd` path is correct. Restart Claude Code. Run `claude mcp list` to verify registration.

### Graphiti import errors
Graphiti degrades gracefully. If `graphiti_core` or `kuzu` has import issues, the system falls back to ChromaDB-only search.

### Telegram bot won't respond
Check: is session running with `--channels` flag? Is the bot paired? Run `/telegram:access` to check status.

### Synapsis cron not running
Check `crontab -l` for the entry. Check `/tmp/daimonion-synapsis.log` for errors. Ensure the script uses absolute paths (no `cd` needed — the script handles its own chdir).

### MEMORY.md not updating
MEMORY.md is written by Synapsis at the end of each pipeline run. If it is stale, run `python scripts/run_synapsis.py` manually. Check the run report in `~/.daimonion/vault/synapsis-runs/` for errors.

## Platform

Tested on macOS (Apple Silicon / M1). Should work on Linux. Windows untested.

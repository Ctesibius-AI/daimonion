"""
Daimonion Configuration — all paths and constants in one place.

Every module imports from here. No hardcoded paths anywhere else.
"""

import os

# ─── Data Directory ──────────────────────────────────────────────────
DATA_DIR = os.path.expanduser('~/.daimonion')

# Memory & Knowledge
MEMORIES_DIR = os.path.join(DATA_DIR, 'memories')
KNOWLEDGE_DIR = os.path.join(DATA_DIR, 'knowledge')

# Graphiti / Kuzu
GRAPH_DIR = os.path.join(DATA_DIR, 'graph')
GRAPH_DB_PATH = os.path.join(GRAPH_DIR, 'daimonion.kuzu')

# Vault (Obsidian wiki)
VAULT_DIR = os.path.join(DATA_DIR, 'vault')

# Conversations
CONVERSATIONS_DIR = os.path.join(DATA_DIR, 'conversations')
DAILY_LOG_DIR = os.path.join(DATA_DIR, 'daily_logs')

# MemPalace
MEMPALACE_DIR = os.path.join(DATA_DIR, 'mempalace')

# Hot Cache (legacy — replaced by MEMORY.md)
HOT_CACHE_MD = os.path.join(DATA_DIR, 'hot_cache.md')
HOT_CACHE_JSON = os.path.join(DATA_DIR, 'hot_cache.json')

# MEMORY.md — compiled multi-vertex index (AAAK format)
# Written by Synapsis, loaded natively by Claude Code at session start
# Auto-detects Claude Code project path, or override with DAIMONION_MEMORY_MD_PATH
def _detect_memory_md_path() -> str:
    """Find the Claude Code memory path for the Pythia project."""
    override = os.environ.get('DAIMONION_MEMORY_MD_PATH')
    if override:
        return override
    # Scan ~/.claude/projects/ for a daimonion-pythia project
    claude_projects = os.path.expanduser('~/.claude/projects')
    if os.path.isdir(claude_projects):
        for name in os.listdir(claude_projects):
            if 'daimonion-pythia' in name or 'daimonion' in name:
                mem_dir = os.path.join(claude_projects, name, 'memory')
                if os.path.isdir(mem_dir) or 'pythia' in name:
                    return os.path.join(mem_dir, 'MEMORY.md')
    # Fallback: write to data dir
    return os.path.join(DATA_DIR, 'MEMORY.md')

MEMORY_MD_PATH = _detect_memory_md_path()

# Research Queue
RESEARCH_QUEUE_PATH = os.path.join(DATA_DIR, 'research_queue.json')

# Synapsis (Σύναψις) — the connector / processor
SYNAPSIS_RUNS_DIR = os.path.join(DATA_DIR, 'night_runs')  # keep disk path for backward compat
SYNAPSIS_STATS_DIR = DATA_DIR
# Backward-compat aliases (remove after full migration)
NIGHT_RUNS_DIR = SYNAPSIS_RUNS_DIR
NIGHT_STATS_DIR = SYNAPSIS_STATS_DIR

# Monitoring
USAGE_DIR = os.path.join(DATA_DIR, 'usage')
HEALTH_DIR = os.path.join(DATA_DIR, 'health')

# Sessions
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')

# User Interests
USER_INTERESTS_PATH = os.path.join(DATA_DIR, 'user_interests.json')

# ─── Project Directory ───────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Skills
SKILLS_DIR = os.path.join(PROJECT_DIR, 'skills')

# SOUL.md paths
SOUL_SONNET_PATH = os.path.join(SKILLS_DIR, 'identity', 'soul_core.md')
SOUL_OPUS_PATH = os.path.join(SKILLS_DIR, 'identity', 'soul.md')

# Skill Index
SKILL_INDEX_PATH = os.path.join(SKILLS_DIR, 'meta', 'skill_index.yaml')

# Baseline Patterns
BASELINE_PATTERNS_PATH = os.path.join(SKILLS_DIR, 'context', 'baseline_patterns.md')

# ─── Models ──────────────────────────────────────────────────────────
SONNET_MODEL = 'claude-sonnet-4-6'
OPUS_MODEL = 'claude-opus-4-6'
HAIKU_MODEL = 'claude-haiku-4-5-20251001'

# ─── Defaults ────────────────────────────────────────────────────────
DEFAULT_CITY = os.environ.get('DAIMONION_DEFAULT_CITY', 'Athens')
MAX_RESEARCH_TOPICS_PER_NIGHT = 3
MEMORY_ARCHIVE_THRESHOLD = 0.05
DEDUP_SIMILARITY_THRESHOLD = 0.82
CONVERSATION_MAX_TOKENS = 4000

# ─── Ensure directories exist ────────────────────────────────────────
for d in [DATA_DIR, MEMORIES_DIR, KNOWLEDGE_DIR, GRAPH_DIR, VAULT_DIR,
          CONVERSATIONS_DIR, DAILY_LOG_DIR, NIGHT_RUNS_DIR, USAGE_DIR,
          HEALTH_DIR, SESSIONS_DIR]:
    os.makedirs(d, exist_ok=True)

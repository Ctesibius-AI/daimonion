"""
Synapsis Report Generator — Compiles a run report from the action log.

Produces a human-readable markdown report dropped into vault/raw/
for second-brain ingestion. Every Synapsis run produces a report.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from src.config import VAULT_DIR


def compile_report(date: str, action_log: list[dict], results: dict) -> dict:
    """Build a markdown report from the action log and pipeline results.

    Args:
        date: The date this run processed.
        action_log: Structured step log from SynapsisLogger.
        results: The full pipeline results dict.

    Returns:
        Dict with report path and summary.
    """
    lines = [
        f'# Synapsis Run Report — {date}',
        f'*Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*',
        '',
    ]

    # Summary
    total_ms = results.get('total_duration_ms', 0)
    lines.append(f'## Summary')
    lines.append(f'- Duration: {total_ms}ms')
    lines.append(f'- Steps executed: {len(action_log)}')
    errors = [s for s in action_log if s.get('status') == 'error']
    if errors:
        lines.append(f'- Errors: {len(errors)}')
    lines.append('')

    # Step-by-step results
    lines.append('## Steps')
    lines.append('')
    for entry in action_log:
        step = entry.get('step', 'unknown')
        status = entry.get('status', 'unknown')
        duration = entry.get('duration_ms', 0)
        icon = 'x' if status == 'ok' else '!'

        lines.append(f'### [{icon}] {step} ({duration}ms)')

        if status == 'error':
            lines.append(f'**ERROR:** {entry.get("error", "unknown")}')
        else:
            # Show key metrics, skip meta fields
            for k, v in entry.items():
                if k in ('step', 'status', 'duration_ms', 'duration'):
                    continue
                lines.append(f'- {k}: {v}')
        lines.append('')

    # Agent results
    agents = results.get('agents', {})
    if agents:
        lines.append('## Agent Results')
        lines.append('')
        for name, agent_result in agents.items():
            status = agent_result.get('status', 'ok')
            lines.append(f'### {name}: {status}')
            _append_agent_summary(lines, name, agent_result)
            lines.append('')

    # QA findings
    qa = results.get('qa', {})
    if qa and not qa.get('error'):
        lines.append('## QA Findings')
        lines.append(f'- Total: {qa.get("total", 0)}')
        lines.append(f'- Critical: {qa.get("critical", 0)}')
        lines.append(f'- Warning: {qa.get("warning", 0)}')
        lines.append(f'- Info: {qa.get("info", 0)}')
        lines.append('')

    # MEMORY.md index
    mem_index = results.get('agents', {}).get('compiler', {}).get('memory_index', {})
    if not mem_index:
        mem_index = results.get('memory_index', {})
    if mem_index and not mem_index.get('error'):
        lines.append('## MEMORY.md Index')
        lines.append(f'- Entries: {mem_index.get("entries", 0)}')
        lines.append(f'- Window: {mem_index.get("window", "?")}')
        lines.append(f'- Path: {mem_index.get("path", "?")}')
        lines.append('')

    # Write to vault/raw/
    raw_dir = os.path.join(VAULT_DIR, 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    report_path = os.path.join(raw_dir, f'synapsis-report-{date}.md')
    content = '\n'.join(lines) + '\n'
    with open(report_path, 'w') as f:
        f.write(content)

    return {
        'path': report_path,
        'lines': len(lines),
        'errors': len(errors),
    }


def _append_agent_summary(lines: list[str], name: str, result: dict):
    """Add agent-specific summary lines."""
    if name == 'extractor':
        lines.append(f'- Memories: {len(result.get("memories", []))}')
        lines.append(f'- Entities: {len(result.get("entities", []))}')
        lines.append(f'- Directives: {len(result.get("directives", []))}')
    elif name == 'deduplicator':
        lines.append(f'- Kept: {result.get("kept", 0)}')
        lines.append(f'- Deduped: {result.get("deduped", 0)}')
        lines.append(f'- Superseded: {result.get("superseded", 0)}')
    elif name == 'analyzer':
        lines.append(f'- Patterns: {len(result.get("patterns", []))}')
        lines.append(f'- Research flags: {len(result.get("research_flags", []))}')
    elif name == 'researcher':
        lines.append(f'- Topics researched: {result.get("topics_researched", 0)}')
    elif name == 'compiler':
        lines.append(f'- ChromaDB memories: {result.get("chromadb_memories_written", 0)}')
        lines.append(f'- Graphiti entities: {result.get("graphiti_entities_written", 0)}')
        lines.append(f'- Knowledge promoted: {result.get("knowledge_promoted", 0)}')
        lines.append(f'- Decay updated: {result.get("decay_scores_updated", 0)}')
    else:
        # Generic: show status and summary if present
        if result.get('summary'):
            lines.append(f'- Summary: {str(result["summary"])[:200]}')

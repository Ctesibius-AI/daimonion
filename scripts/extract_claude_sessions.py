#!/usr/bin/env python3
"""
Extract Claude Code session conversations into Daimonion daily logs.

Claude Code saves all conversations as JSONL at:
  ~/.claude/projects/<project-hash>/sessions/*.jsonl

This script reads those files and converts them into Daimonion's daily log
format at ~/.daimonion/daily_logs/YYYY-MM-DD.md — the format the Night
Processor expects.

Usage:
    python scripts/extract_claude_sessions.py              # extract today
    python scripts/extract_claude_sessions.py 2026-04-08   # extract specific date
    python scripts/extract_claude_sessions.py all           # extract all unprocessed
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Daimonion project sessions
CLAUDE_PROJECTS_DIR = os.path.expanduser('~/.claude/projects')
DAIMONION_PROJECT = '-Users-pythia-gr-daimonion'
PYTHIA_PROJECT = '-Users-pythia-gr-daimonion-pythia'
HOME_PROJECT = '-Users-pythia-gr'

DAILY_LOG_DIR = os.path.expanduser('~/.daimonion/daily_logs')
PROCESSED_MARKER_DIR = os.path.expanduser('~/.daimonion/session_markers')


def _is_tool_noise(content: str) -> bool:
    """Filter out tool output, code blocks, and build noise.

    Keep: real conversation, decisions, opinions, questions, directives.
    Skip: file listings, code diffs, bash output, import checks, test results.
    """
    # Very long messages are almost always tool output or code
    if len(content) > 2000:
        return True

    # Lines that are mostly code
    lines = content.split('\n')
    code_indicators = 0
    for line in lines[:20]:
        stripped = line.strip()
        if (stripped.startswith(('import ', 'from ', 'def ', 'class ', '```',
                                '$ ', '> ', '  File ', 'Traceback', 'Error',
                                '│', '├', '└', '---', '===', '+++',
                                'PASS', 'FAIL', 'ok', 'tests/',
                                'Successfully installed', 'Requirement'))
            or stripped.endswith(('.py', '.json', '.md', '.yaml'))
            or '/__pycache__/' in stripped
            or '/site-packages/' in stripped):
            code_indicators += 1

    if len(lines) > 3 and code_indicators / min(len(lines), 20) > 0.5:
        return True

    # Messages that are just file paths or listings
    if content.startswith(('/Users/', 'total ', 'drwx', '-rw-')):
        return True

    # Pure acknowledgments from assistant (less than 5 words, no substance)
    words = content.split()
    if len(words) <= 2 and content in ('OK', 'Done.', 'Done', 'Yes.', 'No.'):
        return True

    return False


def find_session_files() -> list[str]:
    """Find all JSONL session files from Daimonion and home projects."""
    files = []
    for project in [DAIMONION_PROJECT, PYTHIA_PROJECT, HOME_PROJECT]:
        project_dir = os.path.join(CLAUDE_PROJECTS_DIR, project)
        if not os.path.exists(project_dir):
            continue
        for fname in os.listdir(project_dir):
            if fname.endswith('.jsonl'):
                files.append(os.path.join(project_dir, fname))
    return sorted(files, key=os.path.getmtime)


def parse_session(filepath: str) -> list[dict]:
    """Parse a Claude Code JSONL session into conversation turns."""
    turns = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only process user and assistant messages
            entry_type = entry.get('type', '')
            if entry_type not in ('user', 'assistant'):
                continue

            message = entry.get('message', {})
            role = message.get('role', '')
            content = message.get('content', '')
            timestamp = entry.get('timestamp', '')

            # Handle content that's a list (tool use responses)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = '\n'.join(text_parts)

            if not content or not isinstance(content, str):
                continue

            content = content.strip()
            if not content:
                continue

            # Filter out tool noise — keep only real conversation
            if _is_tool_noise(content):
                continue

            turns.append({
                'role': role,
                'content': content,
                'timestamp': timestamp,
                'source_file': os.path.basename(filepath),
            })

    return turns


def group_by_date(turns: list[dict]) -> dict[str, list[dict]]:
    """Group conversation turns by date."""
    by_date: dict[str, list[dict]] = {}
    for turn in turns:
        ts = turn.get('timestamp', '')
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
                time_str = dt.strftime('%H:%M')
                turn['time'] = time_str
            except (ValueError, TypeError):
                date_str = 'unknown'
                turn['time'] = '??:??'
        else:
            date_str = 'unknown'
            turn['time'] = '??:??'

        by_date.setdefault(date_str, []).append(turn)

    return by_date


def format_daily_log(date: str, turns: list[dict]) -> str:
    """Format turns into Daimonion daily log Markdown."""
    lines = [f'# Daily Log — {date}\n']

    # Group into conversation exchanges (user + assistant pairs)
    i = 0
    exchange_num = 0
    while i < len(turns):
        turn = turns[i]

        if turn['role'] == 'user':
            exchange_num += 1
            user_text = turn['content']
            time_str = turn['time']

            # Look for the next assistant response
            assistant_text = ''
            if i + 1 < len(turns) and turns[i + 1]['role'] == 'assistant':
                assistant_text = turns[i + 1]['content']
                i += 2
            else:
                i += 1

            # Truncate very long messages for the log
            if len(user_text) > 500:
                user_text = user_text[:497] + '...'
            if len(assistant_text) > 1000:
                assistant_text = assistant_text[:997] + '...'

            lines.append(f'\n### [{time_str}] Conversation')
            lines.append(f'**User**: {user_text}')
            if assistant_text:
                lines.append(f'**Pythia**: {assistant_text}')
            lines.append('')
            lines.append('---')
        else:
            # Orphaned assistant message (no preceding user message)
            i += 1

    lines.append(f'\n*Extracted from Claude Code sessions on {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}*')
    return '\n'.join(lines)


def is_processed(session_file: str, date: str) -> bool:
    """Check if a session file has already been processed for a given date."""
    os.makedirs(PROCESSED_MARKER_DIR, exist_ok=True)
    marker = os.path.join(PROCESSED_MARKER_DIR, f'{os.path.basename(session_file)}_{date}.done')
    return os.path.exists(marker)


def mark_processed(session_file: str, date: str):
    """Mark a session file as processed for a given date."""
    os.makedirs(PROCESSED_MARKER_DIR, exist_ok=True)
    marker = os.path.join(PROCESSED_MARKER_DIR, f'{os.path.basename(session_file)}_{date}.done')
    with open(marker, 'w') as f:
        f.write(datetime.now(timezone.utc).isoformat())


def extract(target_date: str | None = None, force: bool = False):
    """Extract Claude Code sessions into daily logs.

    Args:
        target_date: Specific date to extract (YYYY-MM-DD), or None for today, or 'all'
        force: Re-extract even if already processed
    """
    os.makedirs(DAILY_LOG_DIR, exist_ok=True)

    session_files = find_session_files()
    if not session_files:
        print('No Claude Code session files found.')
        return

    print(f'Found {len(session_files)} session files.')

    # Parse all sessions
    all_turns = []
    for filepath in session_files:
        turns = parse_session(filepath)
        if turns:
            all_turns.extend(turns)
            print(f'  {os.path.basename(filepath)}: {len(turns)} turns')

    if not all_turns:
        print('No conversation turns found.')
        return

    # Group by date
    by_date = group_by_date(all_turns)
    print(f'\nDates with conversations: {sorted(by_date.keys())}')

    # Filter to target date
    if target_date and target_date != 'all':
        if target_date not in by_date:
            print(f'No conversations found for {target_date}')
            return
        by_date = {target_date: by_date[target_date]}
    elif target_date != 'all':
        # Default: today
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if today not in by_date:
            print(f'No conversations found for today ({today})')
            return
        by_date = {today: by_date[today]}

    # Write daily logs
    for date, turns in sorted(by_date.items()):
        if date == 'unknown':
            continue

        log_path = os.path.join(DAILY_LOG_DIR, f'{date}.md')

        # Append to existing log (don't overwrite — other interfaces may have written)
        log_content = format_daily_log(date, turns)

        if os.path.exists(log_path):
            # Append with separator
            with open(log_path, 'a') as f:
                f.write(f'\n\n---\n\n# Claude Code Session\n\n')
                # Skip the header line from format_daily_log
                content_lines = log_content.split('\n')[1:]
                f.write('\n'.join(content_lines))
            print(f'  Appended to: {log_path} ({len(turns)} turns)')
        else:
            with open(log_path, 'w') as f:
                f.write(log_content)
            print(f'  Created: {log_path} ({len(turns)} turns)')

    print('\nDone.')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == 'all':
            extract(target_date='all')
        else:
            extract(target_date=arg)
    else:
        extract()

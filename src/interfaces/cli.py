#!/usr/bin/env python3
"""
Pythia CLI — Terminal interface for Daimonion.

Identical to the Telegram pipeline: same PythiaPipeline, same 6 tools,
same Opus escalation, same conversation log, same daily logs, same usage tracking.

Just stdin/stdout instead of Telegram.

Usage:
    cd ~/daimonion
    .venv/bin/python -m src.interfaces.cli
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    level=logging.WARNING,
)
# Only show our logs at INFO
logging.getLogger('daimonion').setLevel(logging.INFO)

logger = logging.getLogger('daimonion.cli')


def print_pythia(text: str):
    """Print Pythia's response with formatting."""
    print(f'\n\033[36mPythia:\033[0m {text}\n')


def print_system(text: str):
    """Print system message."""
    print(f'\033[90m{text}\033[0m')


async def main():
    from src.core.conversation import Conversation
    from src.core.pipeline import PythiaPipeline
    from src.tools.usage_tracker import tracker

    # Check API key
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key or len(api_key) < 10:
        print_system('ANTHROPIC_API_KEY not set in .env')
        sys.exit(1)

    # Initialize
    print_system('Loading Pythia...')

    # Try to initialize retriever (optional)
    retriever = None
    try:
        from src.memory.retrieval import create_retriever
        retriever = create_retriever()
        print_system('Memory retriever: active')
    except Exception:
        print_system('Memory retriever: offline (JSON fallback)')

    pipeline = PythiaPipeline(
        retriever=retriever,
        api_key=api_key,
    )

    conversation = Conversation('cli_session')
    print_system(f'Session: cli_session ({len(conversation)} prior messages)')
    print_system(f'Type "exit" or "quit" to end. "status" for session info.\n')

    # REPL
    while True:
        try:
            user_input = input('\033[33mYou:\033[0m ')
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in ('exit', 'quit', 'bye'):
            print_pythia('Good night.')
            break

        if cmd == 'status':
            summary = tracker.get_today_summary()
            print_system(f'Session: {conversation.get_context_summary()}')
            print_system(f'Skills: {conversation.active_skills or "none"}')
            print_system(f'Opus active: {conversation._opus_active}')
            print_system(f'Today: {summary["total_calls"]} API calls, ${summary["total_cost_usd"]:.4f}')
            continue

        # Add user message
        conversation.add_user_message(user_input, source='cli')

        # Process through pipeline
        t0 = time.time()
        try:
            result = await pipeline.process(conversation, interface=None)
        except Exception as e:
            print_system(f'Error: {e}')
            continue

        elapsed = time.time() - t0
        response = result.get('response', '')
        model = result.get('model', '?')
        tools = [tc['tool'] for tc in result.get('tool_calls', [])]

        if response:
            print_pythia(response)

        # Show metadata
        meta_parts = [f'{model}', f'{elapsed:.1f}s']
        if tools:
            meta_parts.append(f'tools: {", ".join(tools)}')
        print_system(' | '.join(meta_parts))

    # Final stats
    summary = tracker.get_today_summary()
    print_system(f'\nSession ended. {summary["total_calls"]} API calls, ${summary["total_cost_usd"]:.4f} total.')


if __name__ == '__main__':
    asyncio.run(main())

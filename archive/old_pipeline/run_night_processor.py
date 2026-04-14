#!/usr/bin/env python3
"""Run the Night Processor orchestrator.

Usage:
    python scripts/run_night_processor.py              # process today
    python scripts/run_night_processor.py 2026-04-09   # process specific date
    python scripts/run_night_processor.py --topic-index "09:15 — MemPalace storage..."
"""

import asyncio
import json
import logging
import sys

from src.processors.night_orchestrator import NightOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S',
)


async def main():
    date = None
    topic_index = None

    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--topic-index' and i + 1 < len(args):
            topic_index = args[i + 1]
            i += 2
        elif not args[i].startswith('-'):
            date = args[i]
            i += 1
        else:
            i += 1

    orchestrator = NightOrchestrator()
    results = await orchestrator.run(date=date, topic_index=topic_index)

    # Print summary
    print('\n' + '=' * 60)
    print(f'Night Processor — {results["date"]}')
    print(f'Duration: {results["total_duration_ms"]}ms')
    print('=' * 60)

    for agent_name, agent_result in results.get('agents', {}).items():
        status = agent_result.get('status', 'ok')
        duration = agent_result.get('duration_ms', 0)
        print(f'  {agent_name}: {status} ({duration}ms)')

    print()


if __name__ == '__main__':
    asyncio.run(main())

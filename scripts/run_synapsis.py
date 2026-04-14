#!/usr/bin/env python3
"""Run the Synapsis orchestrator.

Usage:
    python scripts/run_synapsis.py                    # process today
    python scripts/run_synapsis.py 2026-04-09         # process specific date
    python scripts/run_synapsis.py --skip-extraction   # skip JSONL → daily log step
    python scripts/run_synapsis.py --topic-index "09:15 — MemPalace storage..."
"""

import asyncio
import json
import logging
import os
import sys

# Ensure we're in the project root (needed for cron and relative imports)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/daimonion/.env'))

from src.processors.synapsis_orchestrator import SynapsisOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S',
)


async def main():
    date = None
    topic_index = None
    skip_extraction = False

    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--topic-index' and i + 1 < len(args):
            topic_index = args[i + 1]
            i += 2
        elif args[i] == '--skip-extraction':
            skip_extraction = True
            i += 1
        elif not args[i].startswith('-'):
            date = args[i]
            i += 1
        else:
            i += 1

    orchestrator = SynapsisOrchestrator()
    results = await orchestrator.run(date=date, topic_index=topic_index, skip_extraction=skip_extraction)

    # Print summary
    print('\n' + '=' * 60)
    print(f'Synapsis — {results["date"]}')
    print(f'Duration: {results["total_duration_ms"]}ms')
    print('=' * 60)

    for agent_name, agent_result in results.get('agents', {}).items():
        status = agent_result.get('status', 'ok')
        duration = agent_result.get('duration_ms', 0)
        print(f'  {agent_name}: {status} ({duration}ms)')

    print()


if __name__ == '__main__':
    asyncio.run(main())

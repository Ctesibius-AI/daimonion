#!/usr/bin/env python3
"""
Run the Night Processor -- Daimonion's nightly pipeline.

Pipeline:
  Step 1: Extract -- Parse daily log, extract memories + knowledge (Haiku)
  Step 2: Analyze -- Cross-reference 7 days of memories (Sonnet)
  Step 3: Research -- Web search on flagged topics (Sonnet)
  Step 4: Compile -- Morning briefing + wiki pages (Haiku)
  Step 5: Update -- Graphiti sync, decay scores, archive (Haiku)
  Step 6: Health -- Check all subsystems, save report

Usage:
  python run_night.py              # process today
  python run_night.py 2026-04-03   # process specific date
  python run_night.py yesterday    # process yesterday
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/daimonion/.env'))

# Ensure project root is on path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

logging.basicConfig(
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger('daimonion.night')


async def main():
    import anthropic

    from src.config import (
        KNOWLEDGE_DIR,
        MEMORIES_DIR,
        NIGHT_RUNS_DIR,
        DATA_DIR,
    )

    client = anthropic.Anthropic()

    # Determine target date
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == 'today':
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        elif arg == 'yesterday':
            date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            date = arg
    else:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    logger.info('Night Processor starting for %s', date)

    # ── Step 1: Extract (Haiku -- memories + knowledge from daily log) ──
    logger.info('Step 1: Extract...')
    from src.processors.night_processor import NightProcessor

    processor = NightProcessor(client=client)
    stats = await processor.run(date=date)

    logger.info('Step 1 complete:')
    for key, val in stats.items():
        logger.info('  %s: %s', key, val)

    # ── Step 2: Analyze (Sonnet -- cross-reference 7 days) ──────────────
    night_runs_dir = os.path.join(NIGHT_RUNS_DIR, date)
    os.makedirs(night_runs_dir, exist_ok=True)

    analysis = None
    step2_path = os.path.join(night_runs_dir, 'step2_analyze.json')
    if os.path.exists(step2_path):
        logger.info('Step 2 already complete -- loading cached result')
        with open(step2_path) as f:
            analysis = json.load(f)
    else:
        logger.info('Step 2: Analyze (7-day cross-reference)...')
        try:
            from src.processors.night_analyzer import analyze
            async_client = anthropic.AsyncAnthropic()

            # Get today's extracted memories for the analyzer
            today_mems = []
            for fname in os.listdir(MEMORIES_DIR):
                if fname.endswith('.json'):
                    try:
                        with open(os.path.join(MEMORIES_DIR, fname)) as f:
                            mem = json.load(f)
                        if mem.get('source_date') == date and not mem.get('archived'):
                            today_mems.append(mem)
                    except (json.JSONDecodeError, IOError):
                        continue

            analysis = await analyze(
                client=async_client,
                today_memories=today_mems,
                target_date=date,
            )

            # Atomic write
            tmp = step2_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(analysis, f, indent=2)
            os.replace(tmp, step2_path)

            stats['analyze_topics'] = len(analysis.get('recurring_topics', []))
            stats['analyze_decisions'] = len(analysis.get('pending_decisions', []))
            stats['analyze_flags'] = len(analysis.get('research_flags', []))
            logger.info('Step 2 complete: %d topics, %d decisions, %d research flags',
                       stats['analyze_topics'], stats['analyze_decisions'], stats['analyze_flags'])
        except Exception as e:
            logger.error('Step 2 (Analyze) failed (non-fatal): %s', e)
            stats['analyze_error'] = str(e)

    # ── Step 3: Research (Sonnet -- flagged topics) ─────────────────────
    research_results = None
    step3_path = os.path.join(night_runs_dir, 'step3_research.json')
    if os.path.exists(step3_path):
        logger.info('Step 3 already complete -- loading cached result')
        with open(step3_path) as f:
            research_results = json.load(f)
    else:
        logger.info('Step 3: Research (flagged topics)...')
        try:
            from src.processors.night_researcher import research
            async_client = anthropic.AsyncAnthropic()

            analyze_flags = analysis.get('research_flags', []) if analysis else []
            research_results = await research(
                client=async_client,
                analyze_flags=analyze_flags,
            )

            # Atomic write
            tmp = step3_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(research_results, f, indent=2)
            os.replace(tmp, step3_path)

            stats['research_topics'] = len(research_results)
            stats['research_ok'] = sum(1 for r in research_results if r.get('status') == 'ok')
            logger.info('Step 3 complete: %d topics researched (%d successful)',
                       stats['research_topics'], stats['research_ok'])
        except Exception as e:
            logger.error('Step 3 (Research) failed (non-fatal): %s', e)
            stats['research_error'] = str(e)

    # ── Step 4: Compile (Haiku -- briefing + wiki) ──────────────────────
    step4_path = os.path.join(night_runs_dir, 'step4_compile.json')
    if os.path.exists(step4_path):
        logger.info('Step 4 already complete -- loading cached result')
    else:
        logger.info('Step 4: Compile (morning briefing + wiki pages)...')
        try:
            from src.processors.night_compiler import compile
            async_client = anthropic.AsyncAnthropic()

            compile_result = await compile(
                client=async_client,
                analysis=analysis,
                research_results=research_results,
                extract_stats=stats,
                target_date=date,
            )

            # Atomic write
            tmp = step4_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(compile_result, f, indent=2)
            os.replace(tmp, step4_path)

            stats['briefing_chars'] = compile_result.get('briefing', {}).get('briefing_length', 0)
            stats['wiki_pages_updated'] = compile_result.get('wiki', {}).get('pages_updated', 0)
            logger.info('Step 4 complete: briefing %d chars, %d wiki pages updated',
                       stats['briefing_chars'], stats['wiki_pages_updated'])
        except Exception as e:
            logger.error('Step 4 (Compile) failed (non-fatal): %s', e)
            stats['compile_error'] = str(e)

    # ── Step 5: Update (Graphiti sync + decay) ──────────────────────────
    # Note: Decay scores are already updated in Step 1 (NightProcessor.run).
    # Graphiti sync is a separate concern -- placeholder for when graph is configured.
    logger.info('Step 5: Update (decay scores updated in Step 1, graph sync pending config)')
    stats['graph_episodes'] = 0
    stats['graph_errors'] = 0

    # ── Step 6: Health Check ────────────────────────────────────────────
    logger.info('Step 6: Health check...')
    try:
        from src.processors.health_monitor import health_check
        health = await health_check(stats, date)
        stats['health_overall'] = health['overall']
        stats['health_checks'] = health['summary']['total_checks']
        stats['health_warnings'] = health['summary']['warning']
        stats['health_critical'] = health['summary']['critical']
        logger.info('Health: %s (%d checks, %d warnings, %d critical)',
                    health['overall'], health['summary']['total_checks'],
                    health['summary']['warning'], health['summary']['critical'])
    except Exception as e:
        logger.error('Health check failed: %s', e)
        stats['health_error'] = str(e)

    # ── Write final stats (atomic) ──────────────────────────────────────
    logger.info('Final stats:')
    for key, val in stats.items():
        logger.info('  %s: %s', key, val)

    stats_path = os.path.join(DATA_DIR, f'night_stats_{date}.json')
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)
    tmp = stats_path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(stats, f, indent=2)
    os.replace(tmp, stats_path)

    logger.info('Night Processor complete for %s', date)


if __name__ == '__main__':
    asyncio.run(main())

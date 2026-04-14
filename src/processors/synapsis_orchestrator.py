"""
Synapsis Orchestrator — Coordinates all 8 agents.

Triggered by "Good Night" (manual) or cron at 3 AM (automated).
Two parallel tracks: intelligence chain (sequential) + information agents (parallel).
Agent 5 (Compiler) waits for all, then writes to all three storage layers.

Architecture:
    Intelligence chain (sequential):
        Agent 1: EXTRACTOR (Sonnet) — four-lens extraction from ChromaDB
        Agent 2: DEDUPLICATOR (Sonnet) — compare against existing, supersession
        Agent 3: ANALYZER (Sonnet) — A5/B2 philosophical lens + drift
        Agent 4: RESEARCHER (Sonnet) — web search on flagged topics

    Information agents (parallel with intelligence chain):
        Agent 6: SPORTS (Haiku)
        Agent 7: NEWS (Haiku)
        Agent 8: WEATHER (Python, no LLM)

    Final:
        Agent 5: COMPILER (Python) — writes to ChromaDB, Graphiti, Vault, hot cache
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import anthropic

from src.config import SONNET_MODEL, HAIKU_MODEL

logger = logging.getLogger('daimonion.synapsis_orchestrator')


class SynapsisOrchestrator:
    """Orchestrates the nightly processing pipeline."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        mempalace_path: str | None = None,
        graphiti_writer=None,
    ):
        self.client = client or anthropic.AsyncAnthropic()
        self.mempalace_path = mempalace_path or '~/.daimonion/mempalace'
        self._graphiti_writer = graphiti_writer

    async def run(self, date: str | None = None, topic_index: str | None = None, skip_extraction: bool = False) -> dict:
        """Run the full Synapsis pipeline.

        Args:
            date: YYYY-MM-DD string. Defaults to today.
            topic_index: The session's topic index (maintained live by Pythia).
                        Passed to the Extractor for conversation flow context.
            skip_extraction: Skip Step 0 (daily log extraction from JSONL).
                           Use when real-time capture is the primary source.

        Returns:
            Summary dict with results from all agents.
        """
        date = date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        t0 = time.time()

        # ─── Night Logger ───
        from src.processors.synapsis_logger import SynapsisLogger
        self.nlog = SynapsisLogger(date)

        logger.info('=== Synapsis starting for %s ===', date)

        # ─── Step 0: Daily log extraction (JSONL → markdown) ───
        if not skip_extraction:
            self.nlog.start('extraction')
            logger.info('Step 0: Extracting daily logs from Claude Code sessions')
            try:
                from scripts.extract_claude_sessions import extract
                extract(target_date=date)
                self.nlog.end('extraction', status='ok')
                logger.info('Step 0 complete: daily log ready for %s', date)
            except Exception as e:
                logger.warning('Step 0 (extraction) failed (non-fatal): %s', e)
                self.nlog.error('extraction', str(e))
        else:
            logger.info('Step 0: Skipped (--skip-extraction)')

        results = {
            'date': date,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'agents': {},
        }

        # MemPalace mining runs after compiler (see below) — non-blocking for intelligence chain.

        # ─── Launch intelligence chain and information agents in parallel ───

        intelligence_task = asyncio.create_task(
            self._run_intelligence_chain(date, topic_index)
        )
        info_task = asyncio.create_task(
            self._run_information_agents(date)
        )

        # Wait for both tracks
        intelligence_results, info_results = await asyncio.gather(
            intelligence_task, info_task
        )

        results['agents'].update(intelligence_results)
        results['agents'].update(info_results)

        # ─── Agent 5: COMPILER — writes to all three layers ───

        self.nlog.start('compiler')
        logger.info('Agent 5: COMPILER — writing to all layers')

        compile_result = await self._run_compiler(
            date=date,
            extract_output=intelligence_results.get('extractor', {}),
            dedup_output=intelligence_results.get('deduplicator', {}),
            analyze_output=intelligence_results.get('analyzer', {}),
            research_output=intelligence_results.get('researcher', {}),
            sports_output=info_results.get('sports', {}),
            news_output=info_results.get('news', {}),
            weather_output=info_results.get('weather', {}),
        )

        results['agents']['compiler'] = compile_result
        results['agents']['compiler']['duration_ms'] = int((time.time() - t0) * 1000)
        self.nlog.end('compiler', status=compile_result.get('status', 'ok'))

        # ─── MemPalace mining — runs after compiler, non-blocking ───

        self.nlog.start('mempalace_mining')
        logger.info('MemPalace mining — per-chunk room detection')
        try:
            from src.memory.convo_miner_ext import mine_convos
            from src.config import DAILY_LOG_DIR, MEMPALACE_DIR
            mine_convos(
                convo_dir=DAILY_LOG_DIR,
                palace_path=MEMPALACE_DIR,
                wing='pythia',
            )
            self.nlog.end('mempalace_mining', status='ok')
            logger.info('MemPalace mining complete')
        except Exception as e:
            logger.warning('MemPalace mining failed (non-fatal): %s', e)
            self.nlog.error('mempalace_mining', str(e))

        # ─── QA Auditor — runs after everything else ───

        self.nlog.start('qa_auditor')
        logger.info('QA AUDITOR — flow verification')
        try:
            from src.processors.qa_auditor import run_audit, get_briefing_line
            qa_report = run_audit(night_result=results)
            results['qa'] = qa_report['summary']
            briefing = get_briefing_line()
            if briefing:
                logger.info('QA: %s', briefing)
            self.nlog.end('qa_auditor',
                          status='ok',
                          findings=qa_report['summary']['total'],
                          critical=qa_report['summary']['critical'],
                          warning=qa_report['summary']['warning'])
        except Exception as e:
            logger.error('QA auditor failed: %s', e)
            results['qa'] = {'error': str(e)}
            self.nlog.error('qa_auditor', str(e))

        # ─── Document Step — compile run report → vault/raw/ ───

        self.nlog.start('document')
        logger.info('DOCUMENT — compiling run report')
        try:
            from src.processors.synapsis_report import compile_report
            # Capture total duration so far for the report
            results['total_duration_ms'] = int((time.time() - t0) * 1000)
            report_result = compile_report(
                date=date,
                action_log=self.nlog.action_log,
                results=results,
            )
            results['report'] = report_result
            self.nlog.end('document', status='ok', lines=report_result['lines'], path=report_result['path'])
            logger.info('Run report: %d lines → %s', report_result['lines'], report_result['path'])
        except Exception as e:
            logger.error('Document step failed: %s', e)
            results['report'] = {'error': str(e)}
            self.nlog.error('document', str(e))

        # ─── Wiki Ingest — route vault/raw/ docs into wiki structure ───

        self.nlog.start('wiki_ingest')
        logger.info('WIKI INGEST — routing raw documents')
        try:
            from src.processors.wiki_ingester import ingest
            ingest_result = ingest()
            results['wiki_ingest'] = ingest_result
            self.nlog.end('wiki_ingest', status='ok',
                          processed=ingest_result['processed'],
                          unclassified=len(ingest_result['unclassified']))
            logger.info('Wiki ingest: %d routed, %d unclassified',
                        ingest_result['processed'], len(ingest_result['unclassified']))
        except Exception as e:
            logger.error('Wiki ingest failed: %s', e)
            results['wiki_ingest'] = {'error': str(e)}
            self.nlog.error('wiki_ingest', str(e))

        # ─── Diary Entries — stats + daily summary (after report + wiki so refs are real) ───

        try:
            from mempalace.palace import get_collection
            from src.config import MEMPALACE_DIR
            col = get_collection(MEMPALACE_DIR)
            compiler_result = results['agents'].get('compiler', {})
            mem_count = compiler_result.get('chromadb_memories_written', 0)
            kb_count = compiler_result.get('knowledge_promoted', 0)
            wiki_pages = compiler_result.get('wiki', {}).get('total_pages', 0)
            qa_findings = results.get('qa', {}).get('total', 0)

            # Stats entry (machine-readable)
            stats_entry = (
                f'SYNAPSIS:{date}|'
                f'mem:{mem_count}|kb:{kb_count}|wiki:{wiki_pages}|'
                f'qa:{qa_findings}|'
                f'dur:{int((time.time() - t0) * 1000)}ms'
            )

            import hashlib
            stats_id = f"diary_wing_pythia_{date}_stats_{hashlib.sha256(stats_entry.encode()).hexdigest()[:12]}"
            col.upsert(
                ids=[stats_id],
                documents=[stats_entry],
                metadatas=[{
                    'wing': 'wing_pythia',
                    'room': 'diary',
                    'hall': 'hall_diary',
                    'type': 'diary_entry',
                    'topic': 'synapsis_stats',
                    'agent': 'pythia',
                    'date': date,
                    'filed_at': datetime.now(timezone.utc).isoformat(),
                }],
            )

            # Daily summary entry — LLM-generated (replaces mechanical truncation)
            extractor = results['agents'].get('extractor', {})
            memories = extractor.get('memories', [])
            analyzer = results['agents'].get('analyzer', {})
            researcher = results['agents'].get('researcher', {})

            # Build input for Haiku summary
            summary_input_parts = [f'Date: {date}', f'Memories extracted: {mem_count}, Knowledge promoted: {kb_count}', '']

            # Memories content
            if memories:
                summary_input_parts.append('## Extracted Memories')
                for m in memories[:15]:
                    content = m.get('content', '') if isinstance(m, dict) else str(m)
                    summary_input_parts.append(f'- {content[:200]}')
                summary_input_parts.append('')

            # Knowledge entries promoted
            kb_entries = []
            import os as _os
            import json as _json
            from src.config import KNOWLEDGE_DIR
            if _os.path.isdir(KNOWLEDGE_DIR):
                for _fname in _os.listdir(KNOWLEDGE_DIR):
                    if _fname.endswith('.json') and date.replace('-', '') in _fname:
                        try:
                            with open(_os.path.join(KNOWLEDGE_DIR, _fname)) as _f:
                                kb_entries.append(_json.load(_f))
                        except Exception:
                            pass
            if kb_entries:
                summary_input_parts.append('## Knowledge Entries Promoted')
                for kb in kb_entries[:10]:
                    summary_input_parts.append(f'- [{kb.get("category", "?")}] {kb.get("fact", "")[:200]}')
                summary_input_parts.append('')

            # Analyzer output — only today's decisions (filter out carried-forward)
            all_decisions = analyzer.get('pending_decisions', analyzer.get('decisions', []))
            today_decisions = [d for d in all_decisions
                               if isinstance(d, dict) and d.get('age_days', 0) <= 1]
            if not today_decisions and all_decisions:
                # Fallback: if no age_days field, include all (backward compat)
                today_decisions = [d for d in all_decisions
                                   if not isinstance(d, dict) or 'age_days' not in d]
            patterns = analyzer.get('patterns', [])
            if today_decisions:
                summary_input_parts.append('## Decisions (today)')
                for d in today_decisions[:5]:
                    summary_input_parts.append(f'- {d if isinstance(d, str) else d.get("decision", d.get("topic", str(d)))}')
            if patterns:
                summary_input_parts.append('## Patterns')
                for p in patterns[:5]:
                    summary_input_parts.append(f'- {p if isinstance(p, str) else p.get("pattern", p.get("description", str(p)))}')

            # Directives
            directives = extractor.get('directives', [])
            if directives:
                summary_input_parts.append('## Directives')
                for d in directives[:5]:
                    summary_input_parts.append(f'- {d if isinstance(d, str) else d.get("content", str(d))}')

            # Research
            research_results = researcher.get('results', [])
            if research_results:
                summary_input_parts.append('## Research Completed')
                for r in research_results[:3]:
                    if isinstance(r, dict):
                        summary_input_parts.append(f'- {r.get("topic", r.get("query", str(r)))}')

            # QA findings
            qa = results.get('qa', {})
            if qa and not qa.get('error') and qa.get('total', 0) > 0:
                summary_input_parts.append(f'## QA Findings: {qa["total"]} ({qa.get("critical", 0)} critical, {qa.get("warning", 0)} warning)')

            summary_input = '\n'.join(summary_input_parts)

            # One Haiku call to produce the diary summary
            try:
                summary_response = await self.client.messages.create(
                    model=HAIKU_MODEL,
                    max_tokens=400,
                    system=(
                        'You write daily diary entries for an AI thinking partner. '
                        'Given the day\'s extracted data, write a concise summary (max 150 words). '
                        'Structure: WORKED ON (what was discussed/built), DECIDED (key decisions), '
                        'COMPLETED (milestones/technical achievements), FLAGGED (issues/QA findings). '
                        'Skip empty sections. Use specific names, not vague descriptions. '
                        'This entry is read at the start of the next session as the briefing.'
                    ),
                    messages=[{'role': 'user', 'content': summary_input}],
                )
                llm_summary = summary_response.content[0].text.strip()
            except Exception as e:
                logger.warning('Haiku diary summary failed, falling back to mechanical: %s', e)
                llm_summary = f'DAY:{date} | mem:{mem_count} | kb:{kb_count} | qa:{qa_findings}'

            # Append structured refs (machine-readable, for lookup)
            ref_parts = []
            mem_ids = [f"mem_{date.replace('-', '')}_{hashlib.md5(m.get('content', '').encode()).hexdigest()[:8]}"
                       for m in memories[:5] if isinstance(m, dict)]
            if mem_ids:
                ref_parts.append(f'mp:{",".join(mem_ids[:3])}')
            else:
                ref_parts.append('mp:N/A')
            kb_count_ref = compiler_result.get('knowledge_promoted', 0)
            ref_parts.append(f'kb:{kb_count_ref}_promoted' if kb_count_ref else 'kb:N/A')
            gr_entities = compiler_result.get('graphiti_entities_written', 0)
            ref_parts.append(f'gr:{gr_entities}_entities' if gr_entities else 'gr:TBD')
            report = results.get('report', {})
            report_path = report.get('path', '')
            if report_path:
                ref_parts.append(f'wiki:synapsis-runs/synapsis-report-{date}')
            else:
                ref_parts.append('wiki:TBD')

            summary_entry = f'{llm_summary}\n---\nrefs: {" | ".join(ref_parts)} | mem:{mem_count} | kb:{kb_count}'

            summary_id = f"diary_wing_pythia_{date}_summary_{hashlib.sha256(summary_entry[:50].encode()).hexdigest()[:12]}"
            col.upsert(
                ids=[summary_id],
                documents=[summary_entry],
                metadatas=[{
                    'wing': 'wing_pythia',
                    'room': 'diary',
                    'hall': 'hall_diary',
                    'type': 'diary_entry',
                    'topic': 'daily_summary',
                    'agent': 'pythia',
                    'date': date,
                    'filed_at': datetime.now(timezone.utc).isoformat(),
                }],
            )

            logger.info('Diary entries written for %s (stats + summary)', date)
        except Exception as e:
            logger.warning('Diary write failed (non-fatal): %s', e)

        # ─── Summary ───

        results['total_duration_ms'] = int((time.time() - t0) * 1000)
        results['completed_at'] = datetime.now(timezone.utc).isoformat()
        results['log_path'] = self.nlog.log_path

        self.nlog.night_complete(results['total_duration_ms'])

        logger.info(
            '=== Synapsis complete: %dms ===',
            results['total_duration_ms'],
        )

        return results

    async def _run_intelligence_chain(self, date: str, topic_index: str | None) -> dict:
        """Run Agents 1-4 sequentially (each depends on previous output)."""
        results = {}

        # Agent 1: EXTRACTOR
        self.nlog.start('extractor')
        logger.info('Agent 1: EXTRACTOR — four-lens extraction from ChromaDB')
        extract_output = await self._run_extractor(date, topic_index)
        extract_output['duration_ms'] = int((time.time() - self.nlog._step_starts.get('extractor', time.time())) * 1000)
        results['extractor'] = extract_output
        mem_count = len(extract_output.get('memories', []))
        ent_count = len(extract_output.get('entities', []))
        dir_count = len(extract_output.get('directives', []))
        self.nlog.end('extractor', status='ok', memories=mem_count, entities=ent_count, directives=dir_count)
        logger.info('Agent 1 done: %d memories, %d entities, %d directives', mem_count, ent_count, dir_count)

        # Agent 2: DEDUPLICATOR
        self.nlog.start('deduplicator')
        logger.info('Agent 2: DEDUPLICATOR — compare against existing')
        dedup_output = await self._run_deduplicator(extract_output)
        results['deduplicator'] = dedup_output
        kept = dedup_output.get('kept', 0)
        deduped = dedup_output.get('deduped', 0)
        superseded = dedup_output.get('superseded', 0)
        self.nlog.end('deduplicator', status='ok', kept=kept, deduped=deduped, superseded=superseded)
        logger.info('Agent 2 done: %d kept, %d deduped, %d superseded', kept, deduped, superseded)

        # Agent 3: ANALYZER
        self.nlog.start('analyzer')
        logger.info('Agent 3: ANALYZER — philosophical lens + drift detection')
        analyze_output = await self._run_analyzer(date, extract_output, dedup_output)
        results['analyzer'] = analyze_output
        patterns = len(analyze_output.get('patterns', []))
        flags = len(analyze_output.get('research_flags', []))
        phil = len(analyze_output.get('new_philosophical_entries', []))
        self.nlog.end('analyzer', status='ok', patterns=patterns, research_flags=flags, philosophical=phil)
        logger.info('Agent 3 done: %d patterns, %d research flags, %d philosophical entries', patterns, flags, phil)

        # Agent 4: RESEARCHER — runs always (reads daytime queue + analyzer flags)
        self.nlog.start('researcher')
        research_flags = analyze_output.get('research_flags', [])
        logger.info('Agent 4: RESEARCHER — %d analyzer flags + daytime queue', len(research_flags))
        research_output = await self._run_researcher(research_flags)
        results['researcher'] = research_output
        researched = research_output.get('topics_researched', 0)
        self.nlog.end('researcher', status=research_output.get('status', 'ok'), topics=researched, analyzer_flags=len(research_flags))

        return results

    async def _run_information_agents(self, date: str) -> dict:
        """Run Agents 6-8 in parallel."""
        results = {}

        self.nlog.start('info_agents')

        # Run all three concurrently
        sports_task = asyncio.create_task(self._run_sports())
        news_task = asyncio.create_task(self._run_news())
        weather_task = asyncio.create_task(self._run_weather())

        sports, news, weather = await asyncio.gather(
            sports_task, news_task, weather_task,
            return_exceptions=True,
        )

        results['sports'] = sports if not isinstance(sports, Exception) else {'status': 'error', 'error': str(sports)}
        results['news'] = news if not isinstance(news, Exception) else {'status': 'error', 'error': str(news)}
        results['weather'] = weather if not isinstance(weather, Exception) else {'status': 'error', 'error': str(weather)}

        sports_ok = 'ok' if not isinstance(sports, Exception) else 'error'
        news_ok = 'ok' if not isinstance(news, Exception) else 'error'
        weather_ok = 'ok' if not isinstance(weather, Exception) else 'error'
        self.nlog.end('info_agents', sports=sports_ok, news=news_ok, weather=weather_ok)

        return results

    # ─── Agent Implementations ────────────────────────────────────────

    async def _run_extractor(self, date: str, topic_index: str | None) -> dict:
        """Agent 1: Four-lens extraction from daily log verbatim.

        Reads today's verbatim from daily log files (single source of truth).
        Extracts through four lenses:
        - A1 (Behavior): communication patterns, corrections, signals
        - A2 (Relationship): boundary shifts, teaching moments, shared language
        - A3 (Design): architecture decisions, intent changes
        - A4 (Philosophy): epistemic standards, decision principles, values

        Returns extracted memories, entities, directives, floor decisions, and
        behavioral/relationship/design/philosophy signals.
        """
        # Read today's verbatim from daily log (primary) or ChromaDB (fallback)
        verbatim = self._read_daily_log(date)
        if not verbatim:
            verbatim = self._read_today_from_chromadb(date)
        if not verbatim:
            return {'memories': [], 'entities': [], 'directives': [],
                    'floors': [], 'signals': {}, 'status': 'no_data'}

        # Build extraction input
        input_text = f'## Date: {date}\n\n'
        if topic_index:
            input_text += f'## Topic Index (conversation flow)\n{topic_index}\n\n'
        input_text += f'## Verbatim ({len(verbatim)} chunks)\n\n'
        for i, chunk in enumerate(verbatim):
            input_text += f'### Chunk {i+1} [{chunk.get("timestamp", "")}]\n'
            input_text += f'Wing: {chunk.get("wing", "")}, Room: {chunk.get("room", "")}\n'
            input_text += chunk.get('content', '') + '\n\n'

        response = await self.client.messages.create(
            model=SONNET_MODEL,
            max_tokens=8192,
            system=EXTRACTOR_PROMPT,
            messages=[{'role': 'user', 'content': input_text}],
        )

        return _parse_json_response(response.content[0].text, default={
            'memories': [], 'entities': [], 'directives': [],
            'floors': [], 'signals': {},
        })

    async def _run_deduplicator(self, extract_output: dict) -> dict:
        """Agent 2: Compare new extractions against existing memories.

        Detects duplicates and supersession using LLM judgment.
        """
        new_memories = extract_output.get('memories', [])
        if not new_memories:
            return {'kept': 0, 'deduped': 0, 'superseded': 0, 'memories': []}

        # Load existing memories from ChromaDB
        existing = self._load_existing_memories_from_chromadb()

        if not existing:
            # First run — everything is new
            return {
                'kept': len(new_memories),
                'deduped': 0,
                'superseded': 0,
                'memories': new_memories,
                'supersession_list': [],
            }

        # Format for LLM comparison
        existing_text = '\n'.join(
            f'- [{m.get("id", "")}] {m.get("content", "")}'
            for m in existing[:50]  # Cap at 50 for context window
        )
        new_text = '\n'.join(
            f'- [NEW_{i}] {m.get("content", "")}'
            for i, m in enumerate(new_memories)
        )

        input_text = f'## Existing Memories ({len(existing)})\n{existing_text}\n\n## New Memories ({len(new_memories)})\n{new_text}'

        response = await self.client.messages.create(
            model=SONNET_MODEL,
            max_tokens=4096,
            system=DEDUPLICATOR_PROMPT,
            messages=[{'role': 'user', 'content': input_text}],
        )

        result = _parse_json_response(response.content[0].text, default={
            'verdicts': [], 'supersession_list': [],
        })

        # Apply verdicts
        kept = []
        deduped = 0
        superseded = 0
        for verdict in result.get('verdicts', []):
            idx = verdict.get('index', -1)
            if 0 <= idx < len(new_memories):
                if verdict.get('verdict') == 'NEW':
                    kept.append(new_memories[idx])
                elif verdict.get('verdict') == 'DUPLICATE':
                    deduped += 1
                elif verdict.get('verdict') == 'SUPERSEDES':
                    kept.append(new_memories[idx])
                    superseded += 1

        # If no verdicts parsed, keep all (safe default)
        if not result.get('verdicts'):
            kept = new_memories

        return {
            'kept': len(kept),
            'deduped': deduped,
            'superseded': superseded,
            'memories': kept,
            'supersession_list': result.get('supersession_list', []),
        }

    async def _run_analyzer(self, date: str, extract_output: dict, dedup_output: dict) -> dict:
        """Agent 3: Philosophical lens + drift detection.

        Combines A5 enrichment (map new patterns to philosophy) with B2 baseline
        comparison (reinforced/drifting/evolved).
        """
        from src.processors.synapsis_analyzer import (
            load_previous_analyses,
            load_baseline_patterns,
            format_previous_analyses,
        )

        # Build input from previous agents
        memories = dedup_output.get('memories', [])
        signals = extract_output.get('signals', {})
        prev_analyses = load_previous_analyses(date, days=7)
        baseline = load_baseline_patterns()

        memories_text = '\n'.join(
            f'- [{m.get("collection", "")}] {m.get("content", "")}'
            for m in memories
        )
        signals_text = ''
        for lens, items in signals.items():
            if items:
                signals_text += f'\n### {lens}\n'
                signals_text += '\n'.join(f'- {s}' for s in items)

        input_text = (
            f'## Date: {date}\n\n'
            f'## Today\'s Memories ({len(memories)})\n{memories_text}\n\n'
            f'## Behavioral/Philosophical Signals\n{signals_text}\n\n'
            f'## Previous 7 Analyses\n{format_previous_analyses(prev_analyses)}\n\n'
        )
        if baseline:
            input_text += f'## Baseline Patterns\n{baseline[:4000]}\n\n'

        response = await self.client.messages.create(
            model=SONNET_MODEL,
            max_tokens=8192,
            system=ANALYZER_PROMPT,
            messages=[{'role': 'user', 'content': input_text}],
        )

        result = _parse_json_response(response.content[0].text, default={
            'recurring_topics': [], 'pending_decisions': [],
            'research_flags': [], 'project_momentum': [],
            'patterns': [], 'baseline_drift': [],
            'new_philosophical_entries': [],
        })

        # Save analysis output for next night's context
        import json, os
        from src.config import NIGHT_RUNS_DIR
        out_dir = os.path.join(NIGHT_RUNS_DIR, date)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'step2_analyze.json')
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2)

        return result

    async def _run_researcher(self, research_flags: list[dict]) -> dict:
        """Agent 4: Web search on flagged topics. Delegates to existing night_researcher."""
        from src.processors.synapsis_researcher import research
        results = await research(
            client=self.client,
            analyze_flags=research_flags,
            model=SONNET_MODEL,
        )
        return {'status': 'ok', 'topics_researched': len(results), 'results': results}

    async def _run_compiler(self, date: str, **agent_outputs) -> dict:
        """Agent 5: Write to all three storage layers. Pure Python + existing compiler."""
        from src.processors.synapsis_compiler import compile
        from src.memory.decay import DecayScorer, MemoryRecord

        extract_output = agent_outputs.get('extract_output', {})
        dedup_output = agent_outputs.get('dedup_output', {})
        analyze_output = agent_outputs.get('analyze_output', {})
        research_output = agent_outputs.get('research_output', {})

        result = {
            'chromadb_memories_written': 0,
            'graphiti_entities_written': 0,
            'vault_pages_updated': 0,
            'floors_assigned': 0,
            'philosophical_entries_added': 0,
            'decay_scores_updated': 0,
        }

        # 1. Write extracted memories to ChromaDB (second collection)
        memories = dedup_output.get('memories', [])
        for mem in memories:
            self._write_memory_to_chromadb(mem, date)
            result['chromadb_memories_written'] += 1

        # 2. Write entities + relations to Graphiti (batch)
        entities = extract_output.get('entities', [])
        memories = dedup_output.get('memories', [])
        graphiti_result = await self._write_all_to_graphiti(entities, memories, date)
        result['graphiti_entities_written'] = graphiti_result.get('nodes_created', 0)
        result['graphiti_edges_written'] = graphiti_result.get('edges_created', 0)
        result['graphiti_episodes_written'] = graphiti_result.get('episodes_written', 0)

        # 3. Assign floor metadata on verbatim drawers
        floors = extract_output.get('floors', [])
        for floor_decision in floors:
            self._assign_floor_to_drawers(floor_decision)
            result['floors_assigned'] += 1

        # 4. Handle supersession
        for superseded_id in dedup_output.get('supersession_list', []):
            self._mark_superseded_in_chromadb(superseded_id)
            # Graphiti invalidation happens via the writer
            if self._graphiti_writer and self._graphiti_writer.available:
                await self._graphiti_writer.invalidate_entity(superseded_id)

        # 5. Write new philosophical entries to permanent layer
        new_philo = analyze_output.get('new_philosophical_entries', [])
        for entry in new_philo:
            self._add_philosophical_entry(entry)
            result['philosophical_entries_added'] += 1

        # 6a. Compile briefing using existing compiler
        compile_result = await compile(
            client=self.client,
            analysis=analyze_output,
            research_results=research_output.get('results', []),
            extract_stats={'memories_written': result['chromadb_memories_written']},
            target_date=date,
        )
        result['briefing'] = compile_result.get('briefing', {})

        # 6b. Bridge knowledge entries to MemPalace (unified search)
        from src.memory.mempalace_bridge import bridge_knowledge_entry
        from src.config import KNOWLEDGE_DIR, MEMPALACE_DIR
        import json as _json
        kb_bridged = 0
        if os.path.isdir(KNOWLEDGE_DIR):
            for _fname in os.listdir(KNOWLEDGE_DIR):
                if _fname.endswith('.json'):
                    try:
                        with open(os.path.join(KNOWLEDGE_DIR, _fname)) as _f:
                            _entry = _json.load(_f)
                        bridge_knowledge_entry(_entry, MEMPALACE_DIR)
                        kb_bridged += 1
                    except Exception:
                        pass
        result['knowledge_bridged'] = kb_bridged

        # 7. Update adaptive traits if drift confirmed
        drift_entries = analyze_output.get('baseline_drift', [])
        confirmed_drift = [d for d in drift_entries
                          if d.get('status') in ('drifting', 'evolved')
                          and d.get('confirmed_nights', 0) >= 3]
        for drift in confirmed_drift:
            self._update_adaptive_trait(drift, date)
            result.setdefault('traits_updated', 0)
            result['traits_updated'] += 1

        # 8. Promote high-significance memories to knowledge
        result['knowledge_promoted'] = self._promote_to_knowledge(memories, date)

        # 8b. KB→Graphiti promotion removed: Step 2 now writes memories via
        # GraphitiWriter.write_episode (Haiku), so entities are already extracted.
        # Promoting KB separately would double-write the same content.

        # 9. Decay scores on existing memories
        result['decay_scores_updated'] = self._update_decay_scores()

        # 10. Build MEMORY.md (AAAK multi-vertex index)
        try:
            from src.processors.memory_index_compiler import compile_memory_index
            index_result = compile_memory_index(date=date)
            result['memory_index'] = index_result
            logger.info('MEMORY.md compiled: %d entries → %s', index_result['entries'], index_result['path'])
        except Exception as e:
            logger.error('MEMORY.md compilation failed: %s', e)
            result['memory_index'] = {'error': str(e)}

        return result

    async def _run_sports(self) -> dict:
        """Agent 6: Sports news filtered by user interests."""
        import json, os
        from src.config import USER_INTERESTS_PATH

        interests = []
        if os.path.exists(USER_INTERESTS_PATH):
            with open(USER_INTERESTS_PATH) as f:
                data = json.load(f)
                interests = data.get('topics', [])

        sport_interests = [i for i in interests if i.lower() in ('f1', 'formula 1', 'football', 'basketball', 'tennis')]
        if not sport_interests:
            return {'status': 'skipped', 'reason': 'no sport interests'}

        query = f'Latest {", ".join(sport_interests)} results standings news {datetime.now().strftime("%B %Y")}'

        try:
            from src.processors.synapsis_researcher import brave_search, format_search_results
            results = await brave_search(query, num_results=5)
            if not results:
                return {'status': 'no_results'}

            formatted = format_search_results(results)
            response = await self.client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                system='Summarize the sports news below in 3-5 bullet points. Only facts, no commentary. Include scores, standings, upcoming events.',
                messages=[{'role': 'user', 'content': formatted}],
            )
            return {'status': 'ok', 'summary': response.content[0].text, 'interests': sport_interests}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    async def _run_news(self) -> dict:
        """Agent 7: Daily news filtered by user interests."""
        import json, os
        from src.config import USER_INTERESTS_PATH

        interests = []
        if os.path.exists(USER_INTERESTS_PATH):
            with open(USER_INTERESTS_PATH) as f:
                data = json.load(f)
                interests = data.get('topics', [])

        non_sport = [i for i in interests if i.lower() not in ('f1', 'formula 1', 'football', 'basketball', 'tennis')]
        if not non_sport:
            return {'status': 'skipped', 'reason': 'no news interests'}

        query = f'{" OR ".join(non_sport)} latest news {datetime.now().strftime("%B %Y")}'

        try:
            from src.processors.synapsis_researcher import brave_search, format_search_results
            results = await brave_search(query, num_results=5)
            if not results:
                return {'status': 'no_results'}

            formatted = format_search_results(results)
            response = await self.client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                system='Summarize the news below in 3-5 bullet points. Only facts, sourced. Focus on developments that matter for someone following these topics.',
                messages=[{'role': 'user', 'content': formatted}],
            )
            return {'status': 'ok', 'summary': response.content[0].text, 'interests': non_sport}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    async def _run_weather(self) -> dict:
        """Agent 8: Weather forecast. Pure API call, no LLM."""
        try:
            from src.tools.weather import get_weather
            from src.config import DEFAULT_CITY
            weather = get_weather(DEFAULT_CITY)
            return {'status': 'ok', 'forecast': weather, 'city': DEFAULT_CITY}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    # ─── ChromaDB / MemPalace Helpers ─────────────────────────────────

    def _read_today_from_chromadb(self, date: str) -> list[dict]:
        """Read today's verbatim chunks from MemPalace ChromaDB."""
        try:
            import chromadb
            import os
            palace_path = os.path.expanduser(self.mempalace_path)
            client = chromadb.PersistentClient(path=palace_path)
            collection = client.get_collection('mempalace_drawers')

            # Fetch all and filter by date prefix (ChromaDB $gte/$lte only works with numbers)
            results = collection.get(include=['documents', 'metadatas'])

            chunks = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents']):
                    meta = results['metadatas'][i] if results.get('metadatas') else {}
                    ts = meta.get('timestamp', '')
                    if not ts.startswith(date):
                        continue
                    chunks.append({
                        'content': doc,
                        'timestamp': ts,
                        'wing': meta.get('wing', ''),
                        'room': meta.get('room', ''),
                        'id': results['ids'][i] if results.get('ids') else '',
                    })

            # Sort by timestamp
            chunks.sort(key=lambda c: c.get('timestamp', ''))
            return chunks

        except Exception as e:
            logger.warning('ChromaDB read failed: %s', e)
            return []

    def _read_daily_log(self, date: str) -> list[dict]:
        """Read today's verbatim from daily log file (primary source).

        Parses the markdown format:
        ### [HH:MM] Conversation
        **User**: message
        **Pythia**: response
        ---
        """
        import re
        from src.config import DAILY_LOG_DIR

        log_path = os.path.join(DAILY_LOG_DIR, f'{date}.md')
        if not os.path.exists(log_path):
            return []

        with open(log_path) as f:
            content = f.read()

        chunks = []
        blocks = re.split(r'^### ', content, flags=re.MULTILINE)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Extract timestamp from header: [HH:MM] Conversation
            ts_match = re.match(r'\[(\d{2}:\d{2})\]', block)
            timestamp = f'{date}T{ts_match.group(1)}:00' if ts_match else ''

            # Extract user message
            user_match = re.search(
                r'\*\*User\*\*:\s*(.+?)(?=\n\*\*(?:Pythia|Assistant)\*\*:|\n---|\Z)',
                block, re.DOTALL,
            )
            assistant_match = re.search(
                r'\*\*(?:Pythia|Assistant)\*\*:\s*(.+?)(?=\n---|\Z)',
                block, re.DOTALL,
            )

            user_text = user_match.group(1).strip() if user_match else ''
            assistant_text = assistant_match.group(1).strip() if assistant_match else ''

            if user_text:
                chunks.append({
                    'content': f'User: {user_text}\n\nAssistant: {assistant_text}',
                    'timestamp': timestamp,
                    'wing': '',
                    'room': '',
                })

        return chunks

    def _load_existing_memories_from_chromadb(self) -> list[dict]:
        """Load existing extracted memories from ChromaDB (second collection)."""
        try:
            import chromadb
            import os
            palace_path = os.path.expanduser(self.mempalace_path)
            client = chromadb.PersistentClient(path=palace_path)
            collection = client.get_or_create_collection('daimonion_memories')

            results = collection.get(
                include=['documents', 'metadatas'],
                limit=200,
            )

            memories = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents']):
                    meta = results['metadatas'][i] if results.get('metadatas') else {}
                    memories.append({
                        'id': results['ids'][i],
                        'content': doc,
                        **meta,
                    })
            return memories
        except Exception as e:
            logger.warning('ChromaDB memories read failed: %s', e)
            return []

    def _write_memory_to_chromadb(self, memory: dict, date: str):
        """Write an extracted memory to ChromaDB + JSON file."""
        try:
            import chromadb
            import os
            import hashlib
            import json
            from datetime import datetime, timezone
            from src.config import MEMORIES_DIR

            content = memory.get('content', '')
            collection_type = memory.get('collection', 'episodic')
            mem_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            mem_id = f'mem_{date.replace("-", "")}_{mem_hash}'

            # Write to ChromaDB
            palace_path = os.path.expanduser(self.mempalace_path)
            client = chromadb.PersistentClient(path=palace_path)
            collection = client.get_or_create_collection('daimonion_memories')

            collection.upsert(
                ids=[mem_id],
                documents=[content],
                metadatas=[{
                    'collection': collection_type,
                    'source_date': date,
                    'significance': memory.get('significance', 'medium'),
                    'decay_score': 1.0,
                    'correction_factor': 1.0,
                    'floor': memory.get('floor', 0),
                }],
            )

            # Write to JSON file
            json_path = os.path.join(MEMORIES_DIR, f'{mem_id}.json')
            if not os.path.exists(json_path):
                mem_record = {
                    'memory_id': mem_id,
                    'content': content,
                    'collection': collection_type,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'source_date': date,
                    'decay_score': 1.0,
                    'correction_factor': 1.0,
                    'access_count': 0,
                    'archived': False,
                }
                with open(json_path, 'w') as f:
                    json.dump(mem_record, f, indent=2)
        except Exception as e:
            logger.error('Memory write failed: %s', e)

    async def _write_all_to_graphiti(self, entities: list[dict], memories: list[dict], date: str) -> dict:
        """Write entities and memories to Graphiti via Haiku-powered episode extraction.

        Each memory becomes an episode. Haiku extracts real entities and relations.
        Entities from the extractor are bundled into the episode body for context.
        """
        try:
            await self._ensure_graphiti_writer()
        except Exception as e:
            logger.warning('GraphitiWriter not available: %s — skipping graph writes', e)
            return {'status': 'unavailable', 'nodes_created': 0, 'edges_created': 0, 'episodes_written': 0}

        if not self._graphiti_writer or not self._graphiti_writer.available:
            return {'status': 'unavailable', 'nodes_created': 0, 'edges_created': 0, 'episodes_written': 0}

        total_nodes = 0
        total_edges = 0
        episodes_written = 0

        for mem in memories:
            content = mem.get('content', '') if isinstance(mem, dict) else str(mem)
            collection = mem.get('collection', 'episodic') if isinstance(mem, dict) else 'episodic'
            if not content:
                continue

            result = await self._graphiti_writer.write_episode(
                name=f'{collection}: {content[:60]}',
                body=content,
                source_description=f'Synapsis extraction {date}',
                reference_time=datetime.fromisoformat(f'{date}T23:00:00+00:00'),
                floor=mem.get('floor') if isinstance(mem, dict) else None,
            )

            if result.get('status') == 'ok':
                total_nodes += result.get('nodes_created', 0)
                total_edges += result.get('edges_created', 0)
                episodes_written += 1

        return {
            'status': 'ok',
            'nodes_created': total_nodes,
            'edges_created': total_edges,
            'episodes_written': episodes_written,
        }

    async def _promote_knowledge_to_graphiti(self, date: str) -> dict:
        """Promote Knowledge JSON entries to Graphiti via write_episode.

        Uses GraphitiWriter.write_episode (async, Haiku-powered) so Graphiti
        extracts real entities and relations from the knowledge facts.
        Tracks promotion via 'promoted_to_graphiti' flag to avoid re-processing.
        """
        import json as _json
        from src.config import KNOWLEDGE_DIR

        if not os.path.isdir(KNOWLEDGE_DIR):
            return {'promoted': 0, 'skipped': 0}

        try:
            await self._ensure_graphiti_writer()
        except Exception as e:
            logger.warning('GraphitiWriter not available for KB promotion: %s', e)
            return {'promoted': 0, 'skipped': 0, 'error': str(e)}

        if not self._graphiti_writer or not self._graphiti_writer.available:
            return {'promoted': 0, 'skipped': 0, 'error': 'GraphitiWriter unavailable'}

        promoted = 0
        skipped = 0

        for fname in os.listdir(KNOWLEDGE_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(KNOWLEDGE_DIR, fname)
            try:
                with open(fpath) as f:
                    kb = _json.load(f)

                # Skip already promoted (idempotent — safe to re-run)
                if kb.get('promoted_to_graphiti'):
                    skipped += 1
                    continue

                fact = kb.get('fact', '')
                category = kb.get('category', 'general')
                if not fact:
                    continue

                # Write via GraphitiWriter — Haiku extracts entities + relations
                episode_result = await self._graphiti_writer.write_episode(
                    name=f'knowledge_{category}: {fact[:60]}',
                    body=fact,
                    source_description=f'Knowledge promotion {date}',
                    reference_time=datetime.fromisoformat(f'{date}T23:00:00+00:00'),
                )

                if episode_result.get('status') == 'ok':
                    # Mark as promoted
                    kb['promoted_to_graphiti'] = True
                    kb['promoted_at'] = datetime.now(timezone.utc).isoformat()
                    kb['graphiti_nodes'] = episode_result.get('nodes_created', 0)
                    kb['graphiti_edges'] = episode_result.get('edges_created', 0)
                    with open(fpath, 'w') as f:
                        _json.dump(kb, f, indent=2)
                    promoted += 1
                    logger.info('KB promoted: %s (%d nodes, %d edges)',
                                fact[:60], episode_result.get('nodes_created', 0),
                                episode_result.get('edges_created', 0))

            except Exception as e:
                logger.error('KB promotion failed for %s: %s', fname, e)

        logger.info('KB → Graphiti: %d promoted, %d skipped (already done)', promoted, skipped)
        return {'promoted': promoted, 'skipped': skipped}

    # _ensure_direct_writer removed — DirectGraphWriter replaced by GraphitiWriter

    async def _ensure_graphiti_writer(self):
        """Initialize GraphitiWriter on first use. Required for Haiku-powered entity extraction."""
        if self._graphiti_writer is None:
            from src.memory.graphiti_writer import GraphitiWriter
            self._graphiti_writer = GraphitiWriter()
            await self._graphiti_writer.initialize()

    def _write_entity_to_graphiti(self, entity: dict, date: str):
        """Queue entity for Graphiti write. Actual write happens in batch via _write_all_to_graphiti."""
        # Entities are collected and written in batch by the compiler
        pass

    def _assign_floor_to_drawers(self, floor_decision: dict):
        """Assign floor metadata to ChromaDB verbatim drawers."""
        try:
            import chromadb
            import os

            palace_path = os.path.expanduser(self.mempalace_path)
            client = chromadb.PersistentClient(path=palace_path)
            collection = client.get_collection('mempalace_drawers')

            drawer_ids = floor_decision.get('drawer_ids', [])
            floor_num = floor_decision.get('floor', 0)

            for did in drawer_ids:
                # ChromaDB doesn't support metadata-only updates easily,
                # so we get + upsert
                existing = collection.get(ids=[did], include=['documents', 'metadatas'])
                if existing and existing['documents']:
                    meta = existing['metadatas'][0] if existing['metadatas'] else {}
                    meta['floor'] = floor_num
                    collection.upsert(
                        ids=[did],
                        documents=existing['documents'],
                        metadatas=[meta],
                    )
        except Exception as e:
            logger.error('Floor assignment failed: %s', e)

    def _mark_superseded_in_chromadb(self, memory_id: str):
        """Mark an existing memory as superseded in ChromaDB."""
        try:
            import chromadb
            import os

            palace_path = os.path.expanduser(self.mempalace_path)
            client = chromadb.PersistentClient(path=palace_path)
            collection = client.get_or_create_collection('daimonion_memories')

            existing = collection.get(ids=[memory_id], include=['documents', 'metadatas'])
            if existing and existing['documents']:
                meta = existing['metadatas'][0] if existing['metadatas'] else {}
                meta['correction_factor'] = 0.3
                collection.upsert(
                    ids=[memory_id],
                    documents=existing['documents'],
                    metadatas=[meta],
                )
        except Exception as e:
            logger.error('Supersession mark failed: %s', e)

    def _invalidate_graphiti_triple(self, memory_id: str):
        """Queue Graphiti triple invalidation. Actual invalidation happens in _write_all_to_graphiti."""
        # Collected and processed in batch by the compiler
        pass

    def _add_philosophical_entry(self, entry: dict):
        """Add a new philosophical entry to the permanent layer."""
        import os
        from src.config import SKILLS_DIR

        name = entry.get('greek_term', 'unknown').lower().replace(' ', '_')
        path = os.path.join(SKILLS_DIR, 'philosophy', 'skills', f'{name}_new.md')

        content = (
            f'# {entry.get("greek_term", "Unknown")} — {entry.get("principle", "")}\n\n'
            f'*Discovered: {datetime.now().strftime("%Y-%m-%d")}*\n'
            f'*Source: Synapsis analysis*\n\n'
            f'## WHY\n{entry.get("evidence", "")}\n\n'
            f'## HOW\n{entry.get("how_it_connects", "")}\n\n'
            f'## Philosophical Lineage\n{entry.get("philosophical_connection", "")}\n'
        )

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        logger.info('New philosophical entry: %s', path)

    def _update_adaptive_trait(self, drift: dict, date: str):
        """Update a behavioral/communication trait file when drift is confirmed (3+ nights).

        Archives the old version, writes the updated trait.
        """
        import os
        import shutil
        from src.config import SKILLS_DIR

        pattern_name = drift.get('pattern', '')
        status = drift.get('status', '')
        note = drift.get('note', '')

        # Find the trait file that matches this pattern
        trait_dirs = [
            os.path.join(SKILLS_DIR, 'traits', 'thinking'),
            os.path.join(SKILLS_DIR, 'traits', 'communication'),
            os.path.join(SKILLS_DIR, 'traits', 'domains'),
            os.path.join(SKILLS_DIR, 'traits', 'context'),
        ]

        for trait_dir in trait_dirs:
            if not os.path.isdir(trait_dir):
                continue
            for fname in os.listdir(trait_dir):
                if not fname.endswith('.md'):
                    continue
                fpath = os.path.join(trait_dir, fname)
                with open(fpath) as f:
                    content = f.read()

                # Simple match: pattern name appears in the trait file
                if pattern_name.lower() in content.lower():
                    # Archive old version
                    archive_dir = os.path.join(SKILLS_DIR, 'traits', '_archive')
                    os.makedirs(archive_dir, exist_ok=True)
                    archive_name = f'{fname}.{date}.bak'
                    shutil.copy2(fpath, os.path.join(archive_dir, archive_name))

                    # Append drift note to the trait file
                    update_note = (
                        f'\n\n---\n\n'
                        f'*Updated {date} by Synapsis — drift {status}*\n'
                        f'*{note}*\n'
                    )
                    with open(fpath, 'a') as f:
                        f.write(update_note)

                    logger.info('Trait updated: %s (%s: %s)', fname, status, note)
                    return

        logger.warning('No trait file found for pattern: %s', pattern_name)

    def _promote_to_knowledge(self, memories: list[dict], date: str) -> int:
        """Promote high-significance memories to knowledge entries.

        Memories with significance=high and collection in (procedural, identity, insights)
        become knowledge facts. Avoids duplicating existing knowledge.
        """
        import json
        import hashlib
        from src.config import KNOWLEDGE_DIR

        promoted = 0
        for mem in memories:
            sig = mem.get('significance', 'medium')
            collection = mem.get('collection', 'episodic')
            content = mem.get('content', '')

            if sig != 'high' or collection == 'episodic' or not content:
                continue

            # Map collection to knowledge category
            category_map = {
                'identity': 'personal',
                'procedural': 'technical',
                'insights': 'business',
            }
            category = category_map.get(collection, 'technical')

            # Dedup: check if similar knowledge exists
            kb_hash = hashlib.md5(content[:100].encode()).hexdigest()[:8]
            kb_id = f'kb_{date.replace("-", "")}_{kb_hash}'
            kb_path = os.path.join(KNOWLEDGE_DIR, f'{kb_id}.json')

            if os.path.exists(kb_path):
                continue

            kb_entry = {
                'knowledge_id': kb_id,
                'fact': content[:300],
                'category': category,
                'source_date': date,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'confidence': 1.0,
                'promoted_from': 'memory',
            }

            try:
                with open(kb_path, 'w') as f:
                    json.dump(kb_entry, f, indent=2)
                promoted += 1
            except Exception as e:
                logger.error('Knowledge promotion failed: %s', e)

        return promoted

    def _update_decay_scores(self) -> int:
        """Recalculate decay scores on all memories in ChromaDB."""
        try:
            import chromadb
            import os
            from datetime import datetime, timezone
            from src.config import MEMORY_ARCHIVE_THRESHOLD

            palace_path = os.path.expanduser(self.mempalace_path)
            client = chromadb.PersistentClient(path=palace_path)
            collection = client.get_or_create_collection('daimonion_memories')

            results = collection.get(include=['documents', 'metadatas'])
            if not results or not results['ids']:
                return 0

            updated = 0
            now = datetime.now(timezone.utc)

            DECAY_RATES = {
                'identity': 0.999,
                'procedural': 0.997,
                'insights': 0.993,
                'episodic': 0.985,
                'sessions': 0.960,
            }

            for i, mem_id in enumerate(results['ids']):
                meta = results['metadatas'][i] if results.get('metadatas') else {}
                source_date = meta.get('source_date', '')
                collection_type = meta.get('collection', 'episodic')
                correction_factor = meta.get('correction_factor', 1.0)

                if not source_date:
                    continue

                try:
                    created = datetime.fromisoformat(source_date + 'T00:00:00+00:00')
                    days_old = (now - created).days
                except (ValueError, TypeError):
                    continue

                rate = DECAY_RATES.get(collection_type, 0.985)
                new_score = (rate ** days_old) * correction_factor

                meta['decay_score'] = round(new_score, 4)
                if new_score < MEMORY_ARCHIVE_THRESHOLD:
                    meta['archived'] = True

                collection.upsert(
                    ids=[mem_id],
                    documents=[results['documents'][i]],
                    metadatas=[meta],
                )
                updated += 1

            return updated

        except Exception as e:
            logger.error('Decay score update failed: %s', e)
            return 0


# ─── Agent Prompts ────────────────────────────────────────────────────

EXTRACTOR_PROMPT = """You are Synapsis Agent 1: EXTRACTOR.

Read the day's verbatim conversation and extract through FOUR LENSES:

## Lens A1 — Behavior
What communication patterns appeared today? New dialogue acts, corrections, signals, decision moments?

## Lens A2 — Relationship
Any relationship shifts? New boundaries set, shared language introduced, teaching moments, error handling?

## Lens A3 — Design
Any design decisions or intent changes? Architecture changes, anti-patterns set, evolution markers?

## Lens A4 — Philosophy
Any philosophical positions articulated? Epistemic standards, decision principles, values expressed?

## Also Extract:

### MEMORIES (the diary — what happened)
For each memory:
- content: What happened (1-2 sentences)
- collection: identity|procedural|insights|episodic|sessions
- significance: high|medium|low
- philosophical_tag: which philosophical principle this connects to (or null)

### ENTITIES + RELATIONS (for the knowledge graph)
For each entity mentioned:
- name: entity name
- type: project|person|tool|concept
- relations: list of {predicate, object, confidence}

### DIRECTIVES
Look for: remember:, correction:, from now on, always, never, TODO:
- content, type (correction|preference|behavioral|action_item|note), priority, affects

### FLOOR DECISIONS
Did a decision point occur? A correction, direction change, "forget that"?
- description, drawer_ids (which chunks belong to this floor), rationale

### SIGNALS (for drift detection)
Organized by lens:
- behavior: list of behavioral signals observed
- relationship: list of relationship signals
- design: list of design signals
- philosophy: list of philosophical signals

## Output: STRICT JSON

```json
{
  "memories": [...],
  "entities": [...],
  "directives": [...],
  "floors": [...],
  "signals": {
    "behavior": [...],
    "relationship": [...],
    "design": [...],
    "philosophy": [...]
  }
}
```

## Rules
- Only extract what's substantive. Skip greetings, acknowledgments.
- Every memory tagged with which philosophical principle applies (if any).
- Entities must include relations — isolated names are useless.
- Be concise — 1-2 sentences per entry.
- Do NOT invent information not in the verbatim.
- Do NOT extract the same fact twice. If the same topic appears in multiple conversation turns, consolidate into ONE memory entry.
"""

DEDUPLICATOR_PROMPT = """You are Synapsis Agent 2: DEDUPLICATOR.

Compare NEW memories against EXISTING memories. For each new memory, decide:
- NEW: genuinely new information, keep it
- DUPLICATE: says the same thing as an existing memory, skip it
- SUPERSEDES: replaces an existing memory (e.g., "switched to X" supersedes "using Y")

For SUPERSEDES: also list which existing memory_id is superseded.

## Output: STRICT JSON

```json
{
  "verdicts": [
    {"index": 0, "verdict": "NEW", "reason": "..."},
    {"index": 1, "verdict": "DUPLICATE", "reason": "same as mem_xxx"},
    {"index": 2, "verdict": "SUPERSEDES", "reason": "replaces old architecture decision", "supersedes_id": "mem_xxx"}
  ],
  "supersession_list": ["mem_xxx", "mem_yyy"]
}
```
"""

ANALYZER_PROMPT = """You are Synapsis Agent 3: ANALYZER.

You receive today's extracted memories, behavioral/philosophical signals, previous 7 nights' analyses, and baseline patterns.

Your job: UPDATE the running analysis AND check through the philosophical lens.

## Produce:

### 1. RECURRING TOPICS — topics on 2+ days
### 2. PENDING DECISIONS — raised but not resolved
### 3. RESEARCH FLAGS — topics needing actual data (only NEW, not already researched)
### 4. PROJECT MOMENTUM — engagement per project
### 5. PATTERNS — new observations from today only (max 3)
### 6. BASELINE DRIFT — compare today against baseline patterns
  - pattern, status (reinforced|drifting|evolved), note
  - CRITICAL: if drift DIVERGES from the philosophical framework, flag as HIGH PRIORITY
### 7. NEW PHILOSOPHICAL ENTRIES — did today's conversation surface a new connection to Greek philosophy?
  Only if structurally real — the principle must operate the same way as the concept.
  - greek_term, principle, evidence, how_it_connects, philosophical_connection

### 8. PROPETEIA CHECK (προπέτεια — rash assent) — did Pythia skip ἐξέτασις?
  - description, severity (high|medium|low)
  This is the HIGHEST PRIORITY check. Jumping from φαντασία (impression) to νόησις (understanding) without ἐξέτασις (examination) — whether agreeing with the partner or with her own inference.

## Output: STRICT JSON

```json
{
  "recurring_topics": [...],
  "pending_decisions": [...],
  "research_flags": [...],
  "project_momentum": [...],
  "patterns": [...],
  "baseline_drift": [...],
  "new_philosophical_entries": [...],
  "waterfall_violations": [...]
}
```

## Rules
- INCREMENTAL: don't repeat previous nights' findings. Update, evolve, or resolve.
- Waterfall violations are NEVER acceptable. Flag every instance.
- Philosophical entries must be structurally real connections, not keyword matches.
- Be concise. This feeds the morning briefing.
"""


def _parse_json_response(text: str, default: dict) -> dict:
    """Parse LLM JSON response, handling markdown fences."""
    import json
    import re

    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return default

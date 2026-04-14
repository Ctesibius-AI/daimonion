"""
Night Processor Orchestrator — Coordinates all 8 agents.

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

logger = logging.getLogger('daimonion.night_orchestrator')


class NightOrchestrator:
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

    async def run(self, date: str | None = None, topic_index: str | None = None) -> dict:
        """Run the full Night Processor pipeline.

        Args:
            date: YYYY-MM-DD string. Defaults to today.
            topic_index: The session's topic index (maintained live by Pythia).
                        Passed to the Extractor for conversation flow context.

        Returns:
            Summary dict with results from all agents.
        """
        date = date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        t0 = time.time()

        # ─── Night Logger ───
        from src.processors.night_logger import NightLogger
        self.nlog = NightLogger(date)

        logger.info('=== Night Processor starting for %s ===', date)

        results = {
            'date': date,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'agents': {},
        }

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

        # ─── Summary ───

        results['total_duration_ms'] = int((time.time() - t0) * 1000)
        results['completed_at'] = datetime.now(timezone.utc).isoformat()
        results['log_path'] = self.nlog.log_path

        self.nlog.night_complete(results['total_duration_ms'])

        logger.info(
            '=== Night Processor complete: %dms ===',
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
        from src.processors.night_analyzer import (
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
        from src.processors.night_researcher import research
        results = await research(
            client=self.client,
            analyze_flags=research_flags,
            model=SONNET_MODEL,
        )
        return {'status': 'ok', 'topics_researched': len(results), 'results': results}

    async def _run_compiler(self, date: str, **agent_outputs) -> dict:
        """Agent 5: Write to all three storage layers. Pure Python + existing compiler."""
        from src.processors.night_compiler import compile
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

        # 6. Compile briefing + vault using existing compiler
        compile_result = await compile(
            client=self.client,
            analysis=analyze_output,
            research_results=research_output.get('results', []),
            extract_stats={'memories_written': result['chromadb_memories_written']},
            target_date=date,
        )
        result['briefing'] = compile_result.get('briefing', {})
        result['wiki'] = compile_result.get('wiki', {})

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

        # 9. Decay scores on existing memories
        result['decay_scores_updated'] = self._update_decay_scores()

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
            from src.processors.night_researcher import brave_search, format_search_results
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
            from src.processors.night_researcher import brave_search, format_search_results
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
        """Batch write entities and memories to Graphiti.

        Entities are written as structured triplets.
        Memories are written as episodes.
        Uses DirectGraphWriter — writes Sonnet-extracted data directly to Kuzu.
        Zero API calls. Graphiti is kept for search only.
        """
        try:
            self._ensure_direct_writer()
        except Exception as e:
            logger.warning('DirectGraphWriter not available: %s — skipping graph writes', e)
            return {'status': 'unavailable', 'nodes_created': 0, 'edges_created': 0, 'episodes_written': 0}

        if not self._direct_writer or not self._direct_writer.available:
            return {'status': 'unavailable', 'nodes_created': 0, 'edges_created': 0, 'episodes_written': 0}

        # Write entities
        entity_result = self._direct_writer.write_entities(entities, date)

        # Write memories as episodes
        memory_result = self._direct_writer.write_memories_as_episodes(memories, date)

        return {
            'status': 'ok',
            'nodes_created': entity_result.get('nodes_created', 0),
            'nodes_updated': entity_result.get('nodes_updated', 0),
            'edges_created': entity_result.get('edges_created', 0),
            'episodes_written': memory_result.get('episodes_written', 0),
        }

    def _ensure_direct_writer(self):
        """Initialize DirectGraphWriter on first use."""
        if not hasattr(self, '_direct_writer') or self._direct_writer is None:
            from src.memory.direct_graph_writer import DirectGraphWriter
            self._direct_writer = DirectGraphWriter()
            self._direct_writer.initialize()

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
            f'*Source: Night Processor analysis*\n\n'
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
                        f'*Updated {date} by Night Processor — drift {status}*\n'
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

EXTRACTOR_PROMPT = """You are Night Processor Agent 1: EXTRACTOR.

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
"""

DEDUPLICATOR_PROMPT = """You are Night Processor Agent 2: DEDUPLICATOR.

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

ANALYZER_PROMPT = """You are Night Processor Agent 3: ANALYZER.

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

### 8. WATERFALL VIOLATIONS — did Pythia flip a position without investigating?
  - description, severity (high|medium|low)
  This is the HIGHEST PRIORITY check. Agreeing without investigating is the one behavior that breaks trust.

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

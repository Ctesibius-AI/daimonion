#!/usr/bin/env python3
"""
LongMemEval Runner for Daimonion — Full Stack + Graphiti.

Uses MemPalace (drawers + KG) + lightweight Kuzu graph for multi-session.
Claude Sonnet for answering via the retrieval protocol.

Usage:
    python tests/benchmarks/longmemeval_runner.py --questions 500
    python tests/benchmarks/longmemeval_runner.py --questions 50 --type multi-session
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/daimonion/.env'))

import anthropic
import chromadb
import kuzu

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger('longmemeval')

DATA_DIR = os.path.join(PROJECT_ROOT, 'tests', 'benchmarks', 'LongMemEval', 'data')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'tests', 'benchmarks', 'results')
BENCH_PALACE_DIR = os.path.expanduser('~/.daimonion/bench_mempalace')
BENCH_GRAPH_BASE = os.path.expanduser('~/.daimonion/bench_graphs')

MILESTONE_INTERVALS = [10, 25, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500]


def extract_entities(text: str) -> list[str]:
    """Lightweight entity extraction — proper nouns, quoted strings, capitalized phrases."""
    entities = set()
    # Quoted strings
    for m in re.finditer(r"'([^']{2,40})'|\"([^\"]{2,40})\"", text):
        entities.add(m.group(1) or m.group(2))
    # Capitalized multi-word phrases (likely proper nouns)
    for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
        entities.add(m.group(1))
    # Single capitalized words that aren't sentence starters (heuristic: not after ., !, ?)
    for m in re.finditer(r'(?<=[a-z]\s)([A-Z][a-z]{2,})\b', text):
        entities.add(m.group(1))
    return list(entities)


class FullStackAdapter:
    """MemPalace (ChromaDB) + lightweight Kuzu graph per question."""

    def __init__(self):
        self.chroma = chromadb.PersistentClient(path=BENCH_PALACE_DIR)
        self._kuzu_db = None
        self._kuzu_conn = None
        self._reset()

    def _reset(self):
        # ChromaDB
        for name in ['bench_palace_drawers', 'bench_palace_kg']:
            try:
                self.chroma.delete_collection(name)
            except Exception:
                pass
        self.drawers = self.chroma.get_or_create_collection(
            'bench_palace_drawers', metadata={'hnsw:space': 'cosine'},
        )
        self.kg = self.chroma.get_or_create_collection('bench_palace_kg')

        # Kuzu — fresh graph per question (unique path to avoid Kuzu state issues)
        self._graph_path = os.path.join(BENCH_GRAPH_BASE, f'q_{uuid.uuid4().hex[:8]}')
        os.makedirs(BENCH_GRAPH_BASE, exist_ok=True)
        self._kuzu_db = kuzu.Database(self._graph_path)
        self._kuzu_conn = kuzu.Connection(self._kuzu_db)
        self._init_graph_schema()

    def _init_graph_schema(self):
        try:
            self._kuzu_conn.execute(
                'CREATE NODE TABLE IF NOT EXISTS Entity(name STRING, date STRING, session STRING, PRIMARY KEY(name))'
            )
            self._kuzu_conn.execute(
                'CREATE REL TABLE IF NOT EXISTS MENTIONED_WITH(FROM Entity TO Entity, session STRING, date STRING)'
            )
        except Exception:
            pass

    def ingest_history(self, sessions: list[list[dict]], dates: list[str]) -> dict:
        """Ingest chat history into MemPalace drawers + KG + Kuzu graph."""
        drawer_count = 0
        kg_count = 0
        graph_entities = set()
        graph_edges = 0

        for session_idx, (session, date) in enumerate(zip(sessions, dates)):
            session_entities = []

            for turn_idx, turn in enumerate(session):
                role = turn.get('role', 'user')
                content = turn.get('content', '')
                if not content:
                    continue

                drawer_id = f'bench_d_{session_idx}_{turn_idx}_{hashlib.md5(content[:50].encode()).hexdigest()[:8]}'
                doc = f'[{date}] {role}: {content}'
                room = self._detect_room(content)

                self.drawers.upsert(
                    ids=[drawer_id],
                    documents=[doc],
                    metadatas=[{
                        'wing': 'bench', 'room': room, 'role': role,
                        'session_id': str(session_idx), 'date': date,
                        'type': 'conversation',
                        'has_answer': turn.get('has_answer', False),
                    }],
                )
                drawer_count += 1

                if role == 'user' and len(content) > 20:
                    self.kg.upsert(
                        ids=[f'bench_kg_{session_idx}_{turn_idx}'],
                        documents=[content],
                        metadatas=[{'type': 'user_statement', 'date': date, 'session_id': str(session_idx)}],
                    )
                    kg_count += 1

                # Extract entities for graph
                ents = extract_entities(content)
                for e in ents:
                    if e not in graph_entities:
                        try:
                            self._kuzu_conn.execute(
                                'MERGE (n:Entity {name: $name}) SET n.date = $date, n.session = $sess',
                                parameters={'name': e, 'date': date, 'sess': str(session_idx)},
                            )
                            graph_entities.add(e)
                        except Exception:
                            pass
                    session_entities.append(e)

            # Connect entities that appear in the same session (co-occurrence)
            unique_session_ents = list(set(session_entities))
            for i in range(len(unique_session_ents)):
                for j in range(i + 1, min(len(unique_session_ents), i + 5)):
                    try:
                        self._kuzu_conn.execute(
                            'MATCH (a:Entity), (b:Entity) WHERE a.name = $a AND b.name = $b '
                            'CREATE (a)-[:MENTIONED_WITH {session: $sess, date: $date}]->(b)',
                            parameters={
                                'a': unique_session_ents[i], 'b': unique_session_ents[j],
                                'sess': str(session_idx), 'date': date,
                            },
                        )
                        graph_edges += 1
                    except Exception:
                        pass

        return {'drawers': drawer_count, 'kg_entries': kg_count,
                'graph_entities': len(graph_entities), 'graph_edges': graph_edges}

    def search(self, query: str, n_results: int = 15) -> list[str]:
        results = self.drawers.query(query_texts=[query], n_results=n_results, include=['documents', 'metadatas'])
        if not results or not results['documents']:
            return []
        return results['documents'][0]

    def kg_search(self, query: str, n_results: int = 5) -> list[str]:
        results = self.kg.query(query_texts=[query], n_results=n_results, include=['documents', 'metadatas'])
        if not results or not results['documents']:
            return []
        return [f'[{m.get("date", "?")}] {d}' for d, m in zip(results['documents'][0], results['metadatas'][0])]

    def graph_search(self, query: str) -> list[str]:
        """Search the Kuzu graph for entities related to the query."""
        results = []
        # Extract entities from query
        query_entities = extract_entities(query)
        # Also try key nouns from query
        words = [w for w in query.split() if len(w) > 3 and w[0].isupper()]
        query_entities.extend(words)

        for entity in query_entities[:5]:
            try:
                # Find co-occurring entities across sessions
                r = self._kuzu_conn.execute(
                    'MATCH (a:Entity)-[r:MENTIONED_WITH]->(b:Entity) '
                    'WHERE a.name CONTAINS $name '
                    'RETURN a.name, b.name, r.session, r.date LIMIT 10',
                    parameters={'name': entity},
                )
                while r.has_next():
                    row = r.get_next()
                    results.append(f'[Graph {row[3]}] {row[0]} mentioned with {row[1]} (session {row[2]})')
            except Exception:
                pass

            # Reverse direction
            try:
                r = self._kuzu_conn.execute(
                    'MATCH (a:Entity)-[r:MENTIONED_WITH]->(b:Entity) '
                    'WHERE b.name CONTAINS $name '
                    'RETURN a.name, b.name, r.session, r.date LIMIT 10',
                    parameters={'name': entity},
                )
                while r.has_next():
                    row = r.get_next()
                    line = f'[Graph {row[3]}] {row[0]} mentioned with {row[1]} (session {row[2]})'
                    if line not in results:
                        results.append(line)
            except Exception:
                pass

        return results

    def clear(self):
        # Clean up old graph
        old_path = getattr(self, '_graph_path', None)
        if old_path and os.path.exists(old_path):
            try:
                self._kuzu_conn = None
                self._kuzu_db = None
                shutil.rmtree(old_path)
            except Exception:
                pass
        self._reset()

    @staticmethod
    def _detect_room(content: str) -> str:
        c = content.lower()
        if any(w in c for w in ['code', 'program', 'function', 'debug', 'error', 'api']):
            return 'technical'
        if any(w in c for w in ['price', 'cost', 'budget', 'money', 'pay', 'buy', 'sell']):
            return 'business'
        if any(w in c for w in ['feel', 'happy', 'sad', 'worried', 'excited', 'love']):
            return 'personal'
        if any(w in c for w in ['plan', 'schedule', 'meeting', 'project', 'deadline']):
            return 'projects'
        return 'general'


async def answer_question(
    client: anthropic.AsyncAnthropic,
    adapter: FullStackAdapter,
    question: str,
    question_date: str,
    question_type: str,
) -> str:
    """Answer using full retrieval protocol: graph → KG → semantic → Claude."""

    # Step 1: Graph search (entity co-occurrence across sessions — helps multi-session)
    graph_results = []
    if question_type in ('multi-session', 'temporal-reasoning', 'knowledge-update'):
        graph_results = adapter.graph_search(question)

    # Step 2: KG search (user statements)
    kg_results = adapter.kg_search(question, n_results=5)

    # Step 3: Semantic search (broad)
    drawer_results = adapter.search(question, n_results=15)

    # Combine: graph hints first, then KG, then drawers
    all_results = []
    seen = set()
    for r in graph_results[:5]:
        if r[:80] not in seen:
            all_results.append(r)
            seen.add(r[:80])
    for r in kg_results:
        if r[:80] not in seen:
            all_results.append(r)
            seen.add(r[:80])
    for r in drawer_results:
        if r[:80] not in seen:
            all_results.append(r)
            seen.add(r[:80])

    if not all_results:
        return "I don't have information about that in my memory."

    context = '\n'.join(all_results[:25])

    # Step 4: Claude answers
    system_prompt = (
        'You are answering questions about past conversations from memory. '
        'The retrieved context includes conversation excerpts (with dates) and graph connections showing which topics/people appeared together across sessions. '
        'Answer concisely and accurately based ONLY on the provided context. '
        'Pay attention to dates, temporal ordering, and cross-session connections. '
        'For multi-session questions, look for how entities connect across different dates. '
        'If the context does not contain enough information, say "I don\'t have that information." '
        'Do not make up or infer information not in the context.'
    )

    response = await client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=200,
        system=system_prompt,
        messages=[{
            'role': 'user',
            'content': f'Today is {question_date}.\n\nRetrieved from memory:\n{context}\n\nQuestion: {question}',
        }],
    )

    return response.content[0].text.strip()


def print_milestone(completed, total, correct_by_type, total_by_type, elapsed):
    total_correct = sum(correct_by_type.values())
    total_answered = sum(total_by_type.values())
    rate = 100 * total_correct / max(total_answered, 1)
    qps = completed / max(elapsed, 0.1)
    eta = (total - completed) / max(qps, 0.01)

    print(f'\n{"─" * 60}')
    print(f'  MILESTONE: {completed}/{total} ({rate:.1f}%) | {qps:.1f} q/s | ETA: {eta/60:.0f} min')
    for qtype in sorted(total_by_type.keys()):
        c = correct_by_type.get(qtype, 0)
        t = total_by_type[qtype]
        print(f'    {qtype:30s} {c}/{t} ({100*c/max(t,1):.1f}%)')
    print(f'{"─" * 60}\n')


async def run_benchmark(n_questions=500, question_type=None, dataset='oracle'):
    if dataset == 'oracle':
        data_path = os.path.join(DATA_DIR, 'longmemeval_oracle.json')
    else:
        data_path = os.path.join(DATA_DIR, 'longmemeval_s_cleaned.json')

    with open(data_path) as f:
        all_questions = json.load(f)

    if question_type:
        all_questions = [q for q in all_questions if q['question_type'] == question_type]

    questions = all_questions[:n_questions]
    total = len(questions)
    logger.info('Running %d questions (type=%s, stack=MemPalace+Kuzu)', total, question_type or 'all')

    client = anthropic.AsyncAnthropic()
    adapter = FullStackAdapter()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    results_path = os.path.join(RESULTS_DIR, f'longmemeval_graphiti_{timestamp}.jsonl')

    correct_by_type = {}
    total_by_type = {}
    t_start = time.time()
    next_milestone_idx = 0

    with open(results_path, 'w') as rf:
        for i, q in enumerate(questions):
            qid = q['question_id']
            qtype = q['question_type']
            question = q['question']
            expected = q['answer']
            question_date = q['question_date']

            adapter.clear()
            stats = adapter.ingest_history(q['haystack_sessions'], q['haystack_dates'])

            try:
                hypothesis = await answer_question(client, adapter, question, question_date, qtype)
            except Exception as e:
                hypothesis = f'Error: {e}'
                logger.error('Q %s failed: %s', qid, e)

            rf.write(json.dumps({'question_id': qid, 'hypothesis': hypothesis}) + '\n')
            rf.flush()

            expected_lower = str(expected).lower()
            hypothesis_lower = str(hypothesis).lower()
            rough_match = expected_lower in hypothesis_lower or any(
                word in hypothesis_lower for word in expected_lower.split() if len(word) > 3
            )

            total_by_type[qtype] = total_by_type.get(qtype, 0) + 1
            if rough_match:
                correct_by_type[qtype] = correct_by_type.get(qtype, 0) + 1

            status = '✓' if rough_match else '✗'
            logger.info('[%d/%d] %s %s | Q: %s | A: %s | Got: %s | G:%d/%d',
                        i+1, total, status, qtype[:15],
                        question[:45], str(expected)[:25], hypothesis[:45],
                        stats['graph_entities'], stats['graph_edges'])

            completed = i + 1
            if next_milestone_idx < len(MILESTONE_INTERVALS) and completed >= MILESTONE_INTERVALS[next_milestone_idx]:
                print_milestone(completed, total, correct_by_type, total_by_type, time.time() - t_start)
                next_milestone_idx += 1

    elapsed = time.time() - t_start
    total_correct = sum(correct_by_type.values())
    total_questions = sum(total_by_type.values())

    print('\n' + '=' * 60)
    print(f'LongMemEval FINAL — {total_questions} questions in {elapsed/60:.1f} min')
    print(f'Stack: MemPalace (drawers + KG) + Kuzu graph → Claude Sonnet')
    print('=' * 60)
    print(f'\nOverall (rough): {total_correct}/{total_questions} ({100*total_correct/max(total_questions,1):.1f}%)')
    print('\nBy type:')
    for qtype in sorted(total_by_type.keys()):
        c = correct_by_type.get(qtype, 0)
        t = total_by_type[qtype]
        print(f'  {qtype:30s} {c}/{t} ({100*c/max(t,1):.1f}%)')
    print(f'\nResults: {results_path}')

    summary_path = results_path.replace('.jsonl', '_summary.json')
    with open(summary_path, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'total_questions': total_questions,
            'total_correct_rough': total_correct,
            'overall_rough_pct': round(100 * total_correct / max(total_questions, 1), 1),
            'elapsed_seconds': round(elapsed, 1),
            'by_type': {
                qtype: {'correct': correct_by_type.get(qtype, 0), 'total': total_by_type[qtype],
                         'pct': round(100 * correct_by_type.get(qtype, 0) / max(total_by_type[qtype], 1), 1)}
                for qtype in sorted(total_by_type.keys())
            },
            'stack': 'MemPalace (drawers + KG) + Kuzu graph → Claude Sonnet 4.6',
            'dataset': dataset,
        }, f, indent=2)
    print(f'Summary: {summary_path}')
    return results_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--questions', type=int, default=500)
    parser.add_argument('--type', type=str, default=None)
    parser.add_argument('--dataset', type=str, default='oracle', choices=['oracle', 's'])
    asyncio.run(run_benchmark(n_questions=parser.parse_args().questions,
                              question_type=parser.parse_args().type,
                              dataset=parser.parse_args().dataset))


if __name__ == '__main__':
    main()

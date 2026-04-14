"""
Synapsis Step 1: Extract -- Parse daily conversation logs into structured memories and knowledge.

Runs as first step of the nightly pipeline. Reads the day's conversation log and:
  1. Extracts structured memories from conversations (Haiku)
  2. Deduplicates against existing memories (local embeddings)
  3. Detects supersession using LLM judgment (not just embedding similarity)
  4. Promotes significant findings to knowledge entries with source links
  5. Updates decay scores on all active memories
  6. Archives memories below 0.05 threshold

The Synapsis is the write path for Daimonion's memory system.
Conversations flow in through the daily log; structured memories flow out.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

import anthropic

from src.config import (
    DAILY_LOG_DIR,
    HAIKU_MODEL,
    KNOWLEDGE_DIR,
    MEMORIES_DIR,
    NIGHT_RUNS_DIR,
)
from src.memory.decay import ARCHIVE_THRESHOLD, DecayScorer, MemoryRecord
from src.memory.deduplication import Deduplicator, SupersessionDetector, cosine_similarity
from src.tools.usage_tracker import tracker

logger = logging.getLogger('daimonion.synapsis_extractor')

EXTRACTION_PROMPT = """You are the Synapsis. Extract structured memories and knowledge from today's conversation log.

## Instructions

Read the conversation log and extract two types of entries:

### MEMORIES (the diary -- what happened)
Episodic records of events, decisions, discussions. Time-bound.
For each memory, provide:
- content: What happened (1-2 sentences)
- collection: One of: identity, procedural, insights, episodic, sessions
  - identity: personal traits, preferences, relationship patterns
  - procedural: technical decisions, architecture choices, how-to knowledge
  - insights: strategic observations, business conclusions
  - episodic: specific events, conversations, meetings
  - sessions: conversation summaries (short-lived)
- entities: List of project/system/person names mentioned
- significance: high, medium, low (how important is this for future reference?)

### KNOWLEDGE (the library -- what is true)
Factual entries promoted from today's conversations. Persistent.
Only extract knowledge when a clear decision was made or a fact was established.
For each knowledge entry, provide:
- content: The fact or decision (1-2 sentences)
- domain: technical, business, personal
- entities: List of relevant entity names
- source_memory: Which memory this knowledge derives from (by index)

## Output Format -- STRICT JSON

```json
{
  "memories": [
    {
      "content": "Discussed switching from multi-agent to single-model architecture.",
      "collection": "procedural",
      "entities": ["Pythia", "LegacyRouter"],
      "significance": "high"
    }
  ],
  "knowledge": [
    {
      "content": "Pythia uses single-model architecture with composable skill library.",
      "domain": "technical",
      "entities": ["Pythia"],
      "source_memory_index": 0
    }
  ]
}
```

### DIRECTIVES (the orders -- what to change)
Explicit instructions from the user to change behavior, update facts, correct mistakes, or take action.
Look for patterns like:
- "comment: ..." or "note: ..." — user is leaving a note for Pythia
- "remember: ..." or "remember that ..." — explicit memory instruction
- "correction: ..." or "wrong: ..." — user correcting a fact or behavior
- "change ... to ..." — update request
- "from now on ..." or "always ..." or "never ..." — behavioral directive
- "TODO:" or "action:" — action items

For each directive, provide:
- content: What the user wants changed or remembered (exact wording)
- type: One of: correction, preference, behavioral, action_item, note
  - correction: fixes a wrong fact or supersedes old knowledge
  - preference: "I prefer X", "don't do Y", "always do Z"
  - behavioral: changes how Pythia should operate
  - action_item: something that needs to be done
  - note: general note for future reference
- priority: high, medium, low
- affects: What this directive changes (e.g., "soul.md", "vault/projects/project-alpha.md", "memory system", "communication style")

## Output Format -- STRICT JSON

```json
{
  "memories": [...],
  "knowledge": [...],
  "directives": [
    {
      "content": "Change Project Alpha pricing to 350 euros",
      "type": "correction",
      "priority": "high",
      "affects": "vault/projects/project-alpha.md"
    }
  ]
}
```

## Rules
- Only extract what's substantive. Skip greetings, small talk, acknowledgments.
- If nothing significant happened, return empty lists.
- Be concise -- 1-2 sentences per entry.
- Prefer specific facts over vague summaries.
- Do NOT invent information not present in the log.
- Directives are HIGHEST PRIORITY. Never miss a user directive. If in doubt, extract it.
"""

SUPERSESSION_PROMPT = """You are the Synapsis checking for conceptual supersession.

A new memory has been extracted. Compare it against existing memories to determine if the new memory REPLACES or UPDATES any of them conceptually -- even if the wording is completely different.

## New Memory
{new_memory}

## Existing Memories
{existing_memories}

## Instructions
For each existing memory, decide:
- SUPERSEDES: The new memory replaces this one (e.g., "switched to X" supersedes "using Y")
- UNRELATED: Different topic, no conflict
- SUPPLEMENTS: Same topic but additive, not contradictory

Respond with ONLY valid JSON:
```json
{{
  "decisions": [
    {{"memory_id": "mem_001", "verdict": "SUPERSEDES", "reason": "New architecture decision replaces old one"}},
    {{"memory_id": "mem_002", "verdict": "UNRELATED", "reason": "Different topic"}}
  ]
}}
```
"""


def parse_daily_log(log_path: str) -> list[dict]:
    """Parse a daily markdown log into structured entries."""
    if not os.path.exists(log_path):
        return []

    with open(log_path) as f:
        content = f.read()

    entries = []
    # Split by ### headers
    blocks = re.split(r'^### ', content, flags=re.MULTILINE)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        entry = _parse_log_entry(block)
        if entry:
            entries.append(entry)

    return entries


def _parse_log_entry(block: str) -> dict | None:
    """Parse a single log entry block into a structured dict.

    Supports two formats:
      Rich:   ### [HH:MM:SS] Domain: X | Type: Y | Session: Z
      Simple: ### [HH:MM] Conversation
    """
    # Try rich format first
    header_match = re.match(
        r'\[(\d{2}:\d{2}:\d{2})\]\s+Domain:\s+(\w+)\s+\|\s+Type:\s+(\w+)\s+\|\s+Session:\s+(\S+)',
        block,
    )
    if header_match:
        timestamp, domain, qtype, session_id = header_match.groups()
    else:
        # Simple format: [HH:MM] Conversation
        simple_match = re.match(r'\[(\d{2}:\d{2})\]\s+\w+', block)
        if not simple_match:
            return None
        timestamp = simple_match.group(1) + ':00'
        domain = 'general'
        qtype = 'conversation'
        session_id = ''

    delegated = '[DELEGATED]' in block

    # Extract user and assistant messages
    user_match = re.search(
        r'\*\*User\*\*:\s*(.+?)(?=\n\*\*(?:Pythia|Assistant)\*\*:|\n---|\Z)',
        block, re.DOTALL,
    )
    assistant_match = re.search(
        r'\*\*(?:Pythia|Assistant)\*\*:\s*(.+?)(?=\n---|\Z)',
        block, re.DOTALL,
    )

    user_msg = user_match.group(1).strip() if user_match else ''
    assistant_msg = assistant_match.group(1).strip() if assistant_match else ''

    if not user_msg:
        return None

    # Extract cost
    cost_match = re.search(r'\*\*Cost\*\*:\s*\$?([\d.]+|N/A)', block)
    cost = None
    if cost_match and cost_match.group(1) != 'N/A':
        cost = float(cost_match.group(1))

    return {
        'timestamp': timestamp,
        'domain': domain,
        'query_type': qtype,
        'session_id': session_id.rstrip('[DELEGATED]'),
        'delegated': delegated,
        'user_message': user_msg,
        'assistant_response': assistant_msg,
        'cost': cost,
    }


def extract_memories(
    client: anthropic.Anthropic,
    log_entries: list[dict],
    model: str = HAIKU_MODEL,
) -> dict:
    """Use LLM to extract structured memories and knowledge from log entries.

    Returns dict with 'memories' and 'knowledge' lists.
    """
    if not log_entries:
        return {'memories': [], 'knowledge': []}

    # Format log entries as readable text for the LLM
    log_text = _format_entries_for_llm(log_entries)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=EXTRACTION_PROMPT,
        messages=[{'role': 'user', 'content': log_text}],
    )

    tracker.log(response, component='night_extract')
    return _parse_extraction_response(response.content[0].text)


def _format_entries_for_llm(entries: list[dict]) -> str:
    """Format log entries as readable text for LLM extraction."""
    lines = []
    for e in entries:
        delegated = ' [DELEGATED]' if e.get('delegated') else ''
        lines.append(
            f"[{e['timestamp']}] {e['domain']}/{e['query_type']}{delegated}\n"
            f"User: {e['user_message']}\n"
            f"Assistant: {e['assistant_response']}"
        )
    return '\n\n---\n\n'.join(lines)


def _parse_extraction_response(text: str) -> dict:
    """Parse LLM extraction response into memories and knowledge lists."""
    # Strip markdown code fences
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            return {'memories': [], 'knowledge': []}

    result.setdefault('memories', [])
    result.setdefault('knowledge', [])
    result.setdefault('directives', [])
    return result


def detect_supersession_llm(
    client: anthropic.Anthropic,
    new_memory: dict,
    existing_memories: list[dict],
    model: str = HAIKU_MODEL,
) -> list[str]:
    """Use LLM to detect conceptual supersession.

    Unlike embedding similarity, this catches cases where
    "switched to single-model" supersedes "uses multi-agent routing"
    even though the texts are semantically different.

    Returns list of memory_ids that the new memory supersedes.
    """
    if not existing_memories:
        return []

    existing_text = '\n'.join(
        f"- [{m['memory_id']}] {m['content']}"
        for m in existing_memories
    )

    prompt = SUPERSESSION_PROMPT.format(
        new_memory=new_memory['content'],
        existing_memories=existing_text,
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}],
    )

    tracker.log(response, component='night_supersession')
    return _parse_supersession_response(response.content[0].text)


def _parse_supersession_response(text: str) -> list[str]:
    """Parse supersession LLM response. Returns list of superseded memory_ids."""
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            return []

    superseded = []
    for decision in result.get('decisions', []):
        if decision.get('verdict') == 'SUPERSEDES':
            superseded.append(decision['memory_id'])

    return superseded


class SynapsisExtractor:
    """Orchestrates the nightly memory extraction pipeline (Step 1)."""

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        embed_fn=None,
    ):
        self.client = client or anthropic.Anthropic()
        self.embed_fn = embed_fn
        self.scorer = DecayScorer()
        self.deduplicator = Deduplicator(embed_fn=embed_fn)
        self.supersession_detector = SupersessionDetector()

    async def run(self, date: str | None = None) -> dict:
        """Run the full extraction pipeline for a given date.

        Args:
            date: YYYY-MM-DD string. Defaults to today.

        Returns:
            Summary dict with counts of memories extracted, deduped,
            superseded, promoted, archived.
        """
        date = date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        log_path = os.path.join(DAILY_LOG_DIR, f'{date}.md')

        stats = {
            'date': date,
            'log_entries': 0,
            'memories_extracted': 0,
            'memories_deduped': 0,
            'memories_written': 0,
            'supersessions_detected': 0,
            'knowledge_promoted': 0,
            'decay_scores_updated': 0,
            'memories_archived': 0,
            'directives_found': 0,
        }

        # Step 1: Parse daily log
        entries = parse_daily_log(log_path)
        stats['log_entries'] = len(entries)
        if not entries:
            logger.info('No log entries found for %s', date)
            return stats

        # Step 2: Extract memories and knowledge via LLM
        logger.info('Extracting memories from %d log entries', len(entries))
        extracted = extract_memories(self.client, entries)
        stats['memories_extracted'] = len(extracted['memories'])

        # Step 3: Load existing memories for dedup and supersession checks
        existing = self._load_existing_memories()

        # Step 4: Deduplicate and write new memories
        new_memories = []
        for mem in extracted['memories']:
            if self.embed_fn and existing:
                new_emb = await self.embed_fn(mem['content'])
                existing_embs = [
                    (e['memory_id'], e.get('embedding', []))
                    for e in existing if e.get('embedding')
                ]
                should_write, dup_id = self.deduplicator.should_write(
                    mem['content'], new_emb, existing_embs
                )
                if not should_write:
                    logger.debug('Deduped against %s', dup_id)
                    stats['memories_deduped'] += 1
                    continue
                mem['embedding'] = new_emb

            mem['memory_id'] = self._generate_id('mem', date, len(new_memories))
            mem['created_at'] = datetime.now(timezone.utc).isoformat()
            mem['source_date'] = date
            mem['decay_score'] = 1.0
            mem['correction_factor'] = 1.0
            mem['access_count'] = 0
            mem['archived'] = False
            new_memories.append(mem)

        # Step 5: LLM-based supersession detection
        for mem in new_memories:
            if existing:
                superseded_ids = detect_supersession_llm(
                    self.client, mem, existing
                )
                for sid in superseded_ids:
                    self._mark_superseded(sid)
                    stats['supersessions_detected'] += 1

        # Step 6: Write new memories to disk
        for mem in new_memories:
            self._save_memory(mem)
            stats['memories_written'] += 1

        # Step 7: Promote knowledge entries
        for kb in extracted.get('knowledge', []):
            src_idx = kb.get('source_memory_index', 0)
            if src_idx < len(new_memories):
                kb['source_memory_id'] = new_memories[src_idx]['memory_id']
            kb['knowledge_id'] = self._generate_id('kb', date, stats['knowledge_promoted'])
            kb['created_at'] = datetime.now(timezone.utc).isoformat()
            kb['source_date'] = date
            self._save_knowledge(kb)
            stats['knowledge_promoted'] += 1

        # Step 7b: Process directives
        directives = extracted.get('directives', [])
        if directives:
            directives_path = os.path.join(NIGHT_RUNS_DIR, date, 'directives.json')
            os.makedirs(os.path.dirname(directives_path), exist_ok=True)
            for d in directives:
                d['extracted_at'] = datetime.now(timezone.utc).isoformat()
                d['source_date'] = date
                d['status'] = 'pending'
            tmp = directives_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(directives, f, indent=2)
            os.replace(tmp, directives_path)
            stats['directives_found'] = len(directives)
            logger.info('Directives found: %d', len(directives))

            # Corrections become knowledge supersessions
            for d in directives:
                if d.get('type') == 'correction' and d.get('priority') == 'high':
                    kb = {
                        'knowledge_id': self._generate_id('kb', date, stats['knowledge_promoted']),
                        'content': d['content'],
                        'domain': 'directive',
                        'source_date': date,
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'directive_type': d['type'],
                        'affects': d.get('affects', ''),
                    }
                    self._save_knowledge(kb)
                    stats['knowledge_promoted'] += 1

                # Preferences and behavioral directives become identity memories
                if d.get('type') in ('preference', 'behavioral'):
                    mem = {
                        'memory_id': self._generate_id('mem', date, stats['memories_written']),
                        'content': d['content'],
                        'collection': 'identity',
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'source_date': date,
                        'decay_score': 1.0,
                        'correction_factor': 1.0,
                        'access_count': 0,
                        'archived': False,
                        'significance': d.get('priority', 'high'),
                        'directive_type': d['type'],
                    }
                    self._save_memory(mem)
                    stats['memories_written'] += 1

        # Step 8: Update decay scores on all active memories
        all_memories = self._load_existing_memories()
        now = datetime.now(timezone.utc)
        for mem_data in all_memories:
            if mem_data.get('archived'):
                continue
            record = MemoryRecord(
                memory_id=mem_data['memory_id'],
                content=mem_data['content'],
                collection=mem_data.get('collection', 'episodic'),
                created_at=datetime.fromisoformat(mem_data['created_at']),
                access_count=mem_data.get('access_count', 0),
                last_accessed=(
                    datetime.fromisoformat(mem_data['last_accessed'])
                    if mem_data.get('last_accessed') else None
                ),
                correction_factor=mem_data.get('correction_factor', 1.0),
            )
            new_score = self.scorer.calculate(record, now)
            should_archive = self.scorer.should_archive(record, now)

            mem_data['decay_score'] = new_score
            if should_archive:
                mem_data['archived'] = True
                stats['memories_archived'] += 1

            self._save_memory(mem_data)
            stats['decay_scores_updated'] += 1

        logger.info(
            'Extract complete: %d extracted, %d deduped, %d written, %d superseded, %d knowledge, %d archived',
            stats['memories_extracted'], stats['memories_deduped'],
            stats['memories_written'], stats['supersessions_detected'],
            stats['knowledge_promoted'], stats['memories_archived'],
        )

        return stats

    def _load_existing_memories(self) -> list[dict]:
        """Load all existing memory files."""
        if not os.path.exists(MEMORIES_DIR):
            return []
        memories = []
        for fname in os.listdir(MEMORIES_DIR):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(MEMORIES_DIR, fname)) as f:
                        memories.append(json.load(f))
                except (json.JSONDecodeError, IOError):
                    logger.warning('Failed to load memory: %s', fname)
                    continue
        return memories

    def _save_memory(self, mem: dict):
        """Save a memory record to disk (atomic write)."""
        os.makedirs(MEMORIES_DIR, exist_ok=True)
        path = os.path.join(MEMORIES_DIR, f"{mem['memory_id']}.json")
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(mem, f, indent=2)
        os.replace(tmp, path)

    def _save_knowledge(self, kb: dict):
        """Save a knowledge entry to disk (atomic write)."""
        os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
        path = os.path.join(KNOWLEDGE_DIR, f"{kb['knowledge_id']}.json")
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(kb, f, indent=2)
        os.replace(tmp, path)

    def _mark_superseded(self, memory_id: str):
        """Mark an existing memory as superseded (correction_factor=0.3)."""
        path = os.path.join(MEMORIES_DIR, f'{memory_id}.json')
        if not os.path.exists(path):
            return
        with open(path) as f:
            mem = json.load(f)
        mem['correction_factor'] = 0.3
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(mem, f, indent=2)
        os.replace(tmp, path)

    def _generate_id(self, prefix: str, date: str, index: int) -> str:
        """Generate a unique memory/knowledge ID."""
        return f'{prefix}_{date.replace("-", "")}_{index:03d}'

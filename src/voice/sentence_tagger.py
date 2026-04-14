"""
Haiku Sentence Tagger — real-time pivot and intent detection.

Tags each incoming sentence with topic, intent, pivot detection, and
question completeness. Runs async, never blocks the pipeline.

v1: 4 fields (topic, intent, pivot_detected, question_feels_complete)

Design basis:
  - Schlangen & Skantze IU Framework (EACL 2009): COMMIT/REVOKE
  - DeVault et al. (2011): stability-based confidence
  - Kennington et al. (2025): gap in incremental dialogue for LLMs

Failure mode: if Haiku fails or times out (>1500ms), defaults to
  {"topic": null, "intent": null, "pivot_detected": false,
   "question_feels_complete": false}
and the system degrades to pre-tagger behavior (wait for pause, then classify).

Every API call tracked via usage_tracker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time

import anthropic

from src.config import HAIKU_MODEL
from src.tools.usage_tracker import tracker

logger = logging.getLogger('daimonion.tagger')

TAGGER_TIMEOUT = 1.5  # 1500ms — includes cold start overhead; runs async so never blocks pipeline

SAFE_DEFAULT = {
    'topic': None,
    'intent': None,
    'pivot_detected': False,
    'question_feels_complete': False,
}

SYSTEM_PROMPT = """You are a real-time sentence tagger for a voice assistant. You receive one sentence from the user plus recent conversation history.

Output ONLY a JSON object with exactly these 4 fields:

1. "topic" — what the sentence is about (short label, e.g. "nereus_pricing", "weather", "architecture", "greeting"). Use snake_case. null if unclear.
2. "intent" — what the user wants: "question", "status_request", "instruction", "thinking_aloud", "greeting", "callback", "correction". null if unclear.
3. "pivot_detected" — true if this sentence changes the topic from what the user was previously discussing. false if it continues the same topic or is the first sentence.
4. "question_feels_complete" — true if the user seems to have finished asking their question/making their point. false if they seem mid-thought.

Rules:
- Be fast and concise. Output ONLY the JSON, nothing else.
- A pivot means the user switched topics, not just added detail to the same topic.
- "question_feels_complete" should be true when the sentence ends a thought, not just because it's a question.
- If this is the first sentence with no history, pivot_detected is always false.

Example output:
{"topic": "nereus_pricing", "intent": "question", "pivot_detected": false, "question_feels_complete": true}"""


class SentenceTagger:
    """Tags individual sentences with topic, intent, pivot, and completeness."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get('ANTHROPIC_API_KEY')
        )
        self.model = model or HAIKU_MODEL
        self._history: list[dict] = []  # Rolling tagged sentence log

    async def tag(
        self,
        sentence: str,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Tag a single sentence. Returns tag dict.

        Args:
            sentence: The new sentence from the user.
            conversation_history: Last 10-20 exchanges from Conversation.
                Each entry: {"role": "user"|"assistant", "content": "..."}

        Returns:
            Dict with topic, intent, pivot_detected, question_feels_complete.
            On failure/timeout, returns SAFE_DEFAULT.
        """
        t0 = time.time()
        try:
            result = await asyncio.wait_for(
                self._call_haiku(sentence, conversation_history),
                timeout=TAGGER_TIMEOUT,
            )
            latency_ms = int((time.time() - t0) * 1000)
            result['_latency_ms'] = latency_ms
            result['_sentence'] = sentence

            # Track for stability detection
            self._history.append(result)
            if len(self._history) > 20:
                self._history = self._history[-20:]

            logger.info(
                'Tag: %dms | topic=%s intent=%s pivot=%s complete=%s | "%s"',
                latency_ms, result.get('topic'), result.get('intent'),
                result.get('pivot_detected'), result.get('question_feels_complete'),
                sentence[:60],
            )
            return result

        except asyncio.TimeoutError:
            logger.warning('Tagger timeout (>%dms) for: "%s"', int(TAGGER_TIMEOUT * 1000), sentence[:60])
            return {**SAFE_DEFAULT, '_latency_ms': int((time.time() - t0) * 1000), '_sentence': sentence, '_timeout': True}
        except Exception as e:
            logger.warning('Tagger error: %s for: "%s"', e, sentence[:60])
            return {**SAFE_DEFAULT, '_latency_ms': int((time.time() - t0) * 1000), '_sentence': sentence, '_error': str(e)}

    def is_topic_stable(self) -> bool:
        """Check if the last 2+ tags show the same topic — stability signal.

        Per DeVault et al. (2011): act when interpretation stabilizes,
        not after N sentences.
        """
        recent = [h for h in self._history[-3:] if h.get('topic')]
        if len(recent) < 2:
            return False
        return len(set(h['topic'] for h in recent)) == 1

    def get_stable_topic(self) -> str | None:
        """Return the current stable topic, or None if not stable."""
        if not self.is_topic_stable():
            return None
        recent = [h for h in self._history[-3:] if h.get('topic')]
        return recent[-1]['topic'] if recent else None

    def last_tag(self) -> dict | None:
        """Return the most recent tag, or None."""
        return self._history[-1] if self._history else None

    def reset(self):
        """Reset tag history (e.g., on new conversation)."""
        self._history.clear()

    def get_log(self) -> list[dict]:
        """Return full tag history for logging/research."""
        return list(self._history)

    async def _call_haiku(
        self,
        sentence: str,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Call Haiku with the tagger prompt."""
        # Build user message with context
        parts = []

        if conversation_history:
            parts.append('## Recent conversation')
            for entry in conversation_history[-6:]:  # Last 3 exchanges (6 messages) — trimmed for latency
                role = entry.get('role', 'user')
                content = entry.get('content', '')
                if content:
                    # Truncate long messages to save tokens
                    if len(content) > 100:
                        content = content[:97] + '...'
                    parts.append(f'{role}: {content}')

        # Previous tags (give Haiku awareness of topic continuity)
        recent_tags = self._history[-3:]
        if recent_tags:
            parts.append('\n## Previous sentence tags')
            for tag in recent_tags:
                parts.append(f'- topic={tag.get("topic")} intent={tag.get("intent")}')

        parts.append(f'\n## New sentence to tag\n{sentence}')

        user_message = '\n'.join(parts)

        t = time.time()
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_message}],
        )

        # Track usage
        duration_ms = int((time.time() - t) * 1000)
        tracker.log(response, component='sentence_tagger', duration_ms=duration_ms)

        return self._parse_response(response.content[0].text)

    @staticmethod
    def _parse_response(text: str) -> dict:
        """Parse Haiku's JSON response with fallback."""
        text = text.strip()

        # Strip markdown fences
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            brace = text.find('{')
            if brace != -1:
                try:
                    decoder = json.JSONDecoder()
                    result, _ = decoder.raw_decode(text, brace)
                except json.JSONDecodeError:
                    return dict(SAFE_DEFAULT)
            else:
                return dict(SAFE_DEFAULT)

        # Ensure all required fields exist
        result.setdefault('topic', None)
        result.setdefault('intent', None)
        result.setdefault('pivot_detected', False)
        result.setdefault('question_feels_complete', False)

        # Type safety
        result['pivot_detected'] = bool(result['pivot_detected'])
        result['question_feels_complete'] = bool(result['question_feels_complete'])

        return result

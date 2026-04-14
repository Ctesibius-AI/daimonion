"""
Conversation Log — Daimonion's own conversation capture.

File-backed. Persists every write. Survives restarts.
Interface-agnostic: Telegram, voice, or Claude Code can all append.
Also writes daily log files for the Synapsis.

Clean implementation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.config import CONVERSATIONS_DIR, DAILY_LOG_DIR, CONVERSATION_MAX_TOKENS

logger = logging.getLogger('daimonion.conversation')

ATHENS_TZ = ZoneInfo('Europe/Athens')


@dataclass
class Message:
    """A single message in the conversation."""
    role: str          # 'user' or 'assistant'
    content: str       # message text
    timestamp: float   # unix timestamp
    source: str = 'text'   # 'text', 'voice', 'telegram', 'claude_code'
    complete: bool = True  # False for live voice transcript

    @property
    def time_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp, tz=ATHENS_TZ).strftime('%H:%M')


class Conversation:
    """File-backed conversation log.

    Every write persists to disk immediately.
    Writes daily log markdown for Synapsis.
    """

    def __init__(self, session_id: str = 'default'):
        self.session_id = session_id
        self._file_path = os.path.join(CONVERSATIONS_DIR, f'{session_id}.json')
        self.active_skills: list[str] = []
        self._opus_active: bool = False
        self._messages: list[Message] = []
        self._load()

    def _load(self):
        """Load from disk."""
        if not os.path.exists(self._file_path):
            self._messages = []
            return

        try:
            with open(self._file_path) as f:
                data = json.load(f)
            self._messages = [Message(**m) for m in data.get('messages', [])]
            self.active_skills = data.get('active_skills', [])
            self._opus_active = data.get('opus_active', False)
            logger.info('Loaded conversation: %d messages from %s',
                        len(self._messages), self._file_path)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning('Failed to load conversation: %s', e)
            self._messages = []

    def _save(self):
        """Save to disk atomically."""
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        data = {
            'session_id': self.session_id,
            'active_skills': self.active_skills,
            'opus_active': self._opus_active,
            'messages': [asdict(m) for m in self._messages],
            'saved_at': datetime.now(timezone.utc).isoformat(),
        }
        tmp = self._file_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self._file_path)

    def add_user_message(self, text: str, source: str = 'text', complete: bool = True):
        """Add a user message. Persists immediately. Writes to daily log."""
        if not complete and self._messages and not self._messages[-1].complete:
            # Update live transcript
            self._messages[-1].content = text
            self._messages[-1].timestamp = time.time()
        else:
            self._messages.append(Message(
                role='user',
                content=text,
                timestamp=time.time(),
                source=source,
                complete=complete,
            ))
        self._save()

    def add_assistant_message(self, text: str):
        """Add Pythia's response. Persists immediately. Writes to daily log."""
        self._messages.append(Message(
            role='assistant',
            content=text,
            timestamp=time.time(),
            source='pythia',
            complete=True,
        ))
        self._save()
        self._write_daily_log(text)

    def finalize_transcript(self):
        """Mark live voice transcript as complete."""
        if self._messages and not self._messages[-1].complete:
            self._messages[-1].complete = True
            self._save()

    def set_active_skills(self, skills: list[str]):
        """Update active skills (lag-by-one-turn)."""
        if skills != self.active_skills:
            self.active_skills = skills
            self._save()

    def get_pending_user_text(self) -> str | None:
        """Get user text not yet responded to."""
        last_assistant = -1
        for i in range(len(self._messages) - 1, -1, -1):
            if self._messages[i].role == 'assistant':
                last_assistant = i
                break

        parts = []
        for msg in self._messages[last_assistant + 1:]:
            if msg.role == 'user' and msg.content.strip():
                parts.append(msg.content.strip())

        return ' '.join(parts) if parts else None

    def get_messages_for_api(self, max_tokens: int = CONVERSATION_MAX_TOKENS) -> list[dict]:
        """Format as API messages array. Token-capped from most recent."""
        complete = [m for m in self._messages if m.complete and m.content.strip()]

        token_count = 0
        selected = []
        for msg in reversed(complete):
            msg_tokens = len(msg.content) // 4
            if token_count + msg_tokens > max_tokens:
                break
            selected.insert(0, msg)
            token_count += msg_tokens

        # Merge consecutive same-role messages
        messages = []
        for msg in selected:
            if messages and messages[-1]['role'] == msg.role:
                messages[-1]['content'] += ' ' + msg.content
            else:
                messages.append({'role': msg.role, 'content': msg.content})

        return messages

    def silence_gap(self) -> float:
        """Seconds since last user input."""
        for msg in reversed(self._messages):
            if msg.role == 'user':
                return time.time() - msg.timestamp
        return 0.0

    def get_context_summary(self) -> str:
        """One-line summary for logging."""
        n_user = sum(1 for m in self._messages if m.role == 'user')
        n_asst = sum(1 for m in self._messages if m.role == 'assistant')
        return f'{n_user} user + {n_asst} assistant, {self.silence_gap():.1f}s silence'

    def _write_daily_log(self, assistant_text: str):
        """Append exchange to daily log for Synapsis."""
        os.makedirs(DAILY_LOG_DIR, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        daily_path = os.path.join(DAILY_LOG_DIR, f'{date_str}.md')

        user_text = self.get_pending_user_text() or '(no user text)'
        now = datetime.now(ATHENS_TZ)
        timestamp = now.strftime('%H:%M')

        entry = (
            f'\n### [{timestamp}] Conversation\n'
            f'**User**: {user_text}\n'
            f'**Pythia**: {assistant_text}\n'
        )

        with open(daily_path, 'a') as f:
            f.write(entry)

    def __len__(self):
        return len(self._messages)

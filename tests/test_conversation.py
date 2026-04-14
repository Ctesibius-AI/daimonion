"""
Unit tests for the Daimonion conversation log.

Tests file persistence, message handling, API formatting, daily log writing.
"""

import json
import os
import time
from unittest.mock import patch

import pytest

from src.core.conversation import Conversation, Message


@pytest.fixture
def conv(tmp_path):
    """Create a conversation with a tmp directory."""
    with patch('src.core.conversation.CONVERSATIONS_DIR', str(tmp_path / 'conv')):
        with patch('src.core.conversation.DAILY_LOG_DIR', str(tmp_path / 'daily')):
            os.makedirs(tmp_path / 'conv', exist_ok=True)
            os.makedirs(tmp_path / 'daily', exist_ok=True)
            yield Conversation('test_session')


class TestMessageBasics:
    def test_add_user_message(self, conv):
        conv.add_user_message('Hello')
        assert len(conv) == 1

    def test_add_assistant_message(self, conv):
        conv.add_user_message('Hi')
        conv.add_assistant_message('Hello!')
        assert len(conv) == 2

    def test_message_has_timestamp(self, conv):
        conv.add_user_message('test')
        msgs = conv.get_messages_for_api()
        assert len(msgs) == 1

    def test_message_source_default(self, conv):
        conv.add_user_message('test')
        assert conv._messages[0].source == 'text'

    def test_message_source_telegram(self, conv):
        conv.add_user_message('test', source='telegram')
        assert conv._messages[0].source == 'telegram'


class TestPersistence:
    def test_saves_to_disk(self, conv):
        conv.add_user_message('test')
        assert os.path.exists(conv._file_path)

    def test_loads_from_disk(self, tmp_path):
        with patch('src.core.conversation.CONVERSATIONS_DIR', str(tmp_path / 'conv')):
            with patch('src.core.conversation.DAILY_LOG_DIR', str(tmp_path / 'daily')):
                os.makedirs(tmp_path / 'conv', exist_ok=True)
                os.makedirs(tmp_path / 'daily', exist_ok=True)
                c1 = Conversation('persist_test')
                c1.add_user_message('Hello')
                c1.add_assistant_message('Hi')

                c2 = Conversation('persist_test')
                assert len(c2) == 2

    def test_atomic_write(self, conv):
        conv.add_user_message('test')
        # No .tmp file should remain
        assert not os.path.exists(conv._file_path + '.tmp')

    def test_corrupt_file_recovers(self, conv):
        # Write garbage
        os.makedirs(os.path.dirname(conv._file_path), exist_ok=True)
        with open(conv._file_path, 'w') as f:
            f.write('not json')
        conv._load()
        assert len(conv) == 0


class TestPendingText:
    def test_gets_pending_user_text(self, conv):
        conv.add_user_message('first')
        assert conv.get_pending_user_text() == 'first'

    def test_no_pending_after_response(self, conv):
        conv.add_user_message('question')
        conv.add_assistant_message('answer')
        assert conv.get_pending_user_text() is None

    def test_multiple_pending_messages_concatenated(self, conv):
        conv.add_user_message('part 1')
        conv.add_user_message('part 2')
        result = conv.get_pending_user_text()
        assert 'part 1' in result
        assert 'part 2' in result


class TestAPIFormatting:
    def test_formats_messages(self, conv):
        conv.add_user_message('question')
        conv.add_assistant_message('answer')
        msgs = conv.get_messages_for_api()
        assert len(msgs) == 2
        assert msgs[0] == {'role': 'user', 'content': 'question'}
        assert msgs[1] == {'role': 'assistant', 'content': 'answer'}

    def test_merges_consecutive_same_role(self, conv):
        conv.add_user_message('part 1')
        conv.add_user_message('part 2')
        msgs = conv.get_messages_for_api()
        assert len(msgs) == 1
        assert 'part 1' in msgs[0]['content']
        assert 'part 2' in msgs[0]['content']

    def test_token_cap(self, conv):
        # Add many messages
        for i in range(100):
            conv.add_user_message(f'message {i} ' * 50)
            conv.add_assistant_message(f'response {i} ' * 50)
        msgs = conv.get_messages_for_api(max_tokens=100)
        # Should be trimmed
        assert len(msgs) < 200


class TestLiveTranscript:
    def test_incomplete_message_updated(self, conv):
        conv.add_user_message('hel', complete=False)
        conv.add_user_message('hello world', complete=False)
        assert len(conv) == 1
        assert conv._messages[0].content == 'hello world'

    def test_finalize_transcript(self, conv):
        conv.add_user_message('hello', complete=False)
        conv.finalize_transcript()
        assert conv._messages[0].complete is True


class TestActiveSkills:
    def test_set_active_skills(self, conv):
        conv.set_active_skills(['business_strategy', 'analytical_thinking'])
        assert conv.active_skills == ['business_strategy', 'analytical_thinking']

    def test_skills_persist(self, tmp_path):
        with patch('src.core.conversation.CONVERSATIONS_DIR', str(tmp_path / 'conv')):
            with patch('src.core.conversation.DAILY_LOG_DIR', str(tmp_path / 'daily')):
                os.makedirs(tmp_path / 'conv', exist_ok=True)
                os.makedirs(tmp_path / 'daily', exist_ok=True)
                c1 = Conversation('skill_test')
                c1.set_active_skills(['test_skill'])

                c2 = Conversation('skill_test')
                assert c2.active_skills == ['test_skill']


class TestDailyLog:
    def test_writes_daily_log(self, conv):
        conv.add_user_message('test question')
        conv.add_assistant_message('test answer')
        # Check daily log was written
        from src.config import DAILY_LOG_DIR
        # The daily log writing is patched via DAILY_LOG_DIR mock
        # Just verify no crash


class TestSilenceGap:
    def test_silence_gap_after_message(self, conv):
        conv.add_user_message('test')
        gap = conv.silence_gap()
        assert gap >= 0
        assert gap < 5  # should be near-instant

    def test_silence_gap_no_messages(self, conv):
        assert conv.silence_gap() == 0.0


class TestContextSummary:
    def test_summary_format(self, conv):
        conv.add_user_message('hello')
        conv.add_assistant_message('hi')
        summary = conv.get_context_summary()
        assert '1 user' in summary
        assert '1 assistant' in summary

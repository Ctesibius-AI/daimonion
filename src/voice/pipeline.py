"""
Daimonion Voice Pipeline: audio in -> brain -> audio out.

Flow:
  1. WAV/OGG bytes -> Whisper STT -> transcribed text
  2. Text -> PythiaPipeline.process() -> response text
  3. Response text -> Kokoro TTS (bf_isabella) -> WAV bytes

Each step is independent and timed. The pipeline returns both the
audio response and a timing breakdown for diagnostics.

All heavy dependencies (whisper, soundfile, numpy) are optional.
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field

from src.voice.tts import KokoroTTS, KOKORO_SAMPLE_RATE

logger = logging.getLogger('daimonion.voice')

# Optional heavy dependencies
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    whisper = None  # type: ignore[assignment]
    WHISPER_AVAILABLE = False

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None  # type: ignore[assignment]
    SOUNDFILE_AVAILABLE = False

WHISPER_MODEL_SIZE = 'base'


@dataclass
class VoiceResult:
    """Result of a voice pipeline run."""
    transcription: str = ''
    response_text: str = ''
    audio_bytes: bytes = b''
    sample_rate: int = KOKORO_SAMPLE_RATE
    timing: dict = field(default_factory=dict)
    error: str | None = None


class VoicePipeline:
    """End-to-end voice pipeline: audio -> text -> brain -> text -> audio."""

    def __init__(self):
        self._whisper_model = None
        self._tts = KokoroTTS()

    @property
    def stt_available(self) -> bool:
        """Whether Whisper STT is available."""
        return WHISPER_AVAILABLE

    @property
    def tts_available(self) -> bool:
        """Whether Kokoro TTS is available."""
        return self._tts.available

    @property
    def whisper_model(self):
        """Lazy-load Whisper model."""
        if self._whisper_model is None:
            if not WHISPER_AVAILABLE:
                raise RuntimeError('Whisper is not installed')
            logger.info('Loading Whisper model (%s)...', WHISPER_MODEL_SIZE)
            t = time.time()
            self._whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            logger.info('Whisper loaded in %.1fs', time.time() - t)
        return self._whisper_model

    def transcribe(self, audio_path: str) -> tuple[str, float]:
        """Transcribe audio file to text via Whisper.

        Args:
            audio_path: Path to audio file (WAV, OGG, MP3, etc.)

        Returns:
            (transcribed_text, elapsed_seconds)
        """
        t = time.time()
        result = self.whisper_model.transcribe(audio_path)
        elapsed = time.time() - t
        return result['text'].strip(), elapsed

    def synthesize(self, text: str) -> tuple[bytes, float]:
        """Synthesize text to WAV audio bytes via Kokoro.

        Returns:
            (wav_bytes, elapsed_seconds)
        """
        t = time.time()
        wav_bytes = self._tts.synthesize(text)
        elapsed = time.time() - t
        return wav_bytes, elapsed

    async def process(
        self,
        audio_path: str,
        pipeline,
        conversation=None,
        session_id: str | None = None,
    ) -> VoiceResult:
        """Full pipeline: audio file -> transcribe -> think -> speak.

        Args:
            audio_path: Path to input audio file.
            pipeline: PythiaPipeline instance.
            conversation: Optional Conversation instance.
            session_id: Optional session ID (used if no conversation provided).

        Returns:
            VoiceResult with transcription, response, audio, and timing.
        """
        result = VoiceResult()
        t_total = time.time()

        # Step 1: STT
        try:
            result.transcription, stt_time = self.transcribe(audio_path)
            result.timing['stt_ms'] = int(stt_time * 1000)
        except Exception as e:
            result.error = f'STT failed: {e}'
            return result

        if not result.transcription:
            result.error = 'No speech detected'
            return result

        # Step 2: Pipeline
        try:
            t = time.time()

            # Create conversation if needed
            if conversation is None:
                from src.core.conversation import Conversation
                conversation = Conversation(session_id=session_id or 'voice')

            conversation.add_user_message(result.transcription, source='voice')

            pipe_result = await pipeline.process(
                conversation=conversation,
                interface='voice',
            )
            result.response_text = pipe_result.get('response', '')
            result.timing['think_ms'] = int((time.time() - t) * 1000)
        except Exception as e:
            result.error = f'Pipeline failed: {e}'
            return result

        # Step 3: TTS
        try:
            result.audio_bytes, tts_time = self.synthesize(result.response_text)
            result.timing['tts_ms'] = int(tts_time * 1000)
        except Exception as e:
            result.error = f'TTS failed: {e}'
            return result

        result.timing['total_ms'] = int((time.time() - t_total) * 1000)
        return result

    async def process_bytes(
        self,
        audio_bytes: bytes,
        pipeline,
        conversation=None,
        session_id: str | None = None,
        input_format: str = 'wav',
    ) -> VoiceResult:
        """Process raw audio bytes (writes to temp file for Whisper)."""
        import os
        suffix = f'.{input_format}'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            return await self.process(tmp_path, pipeline, conversation, session_id)
        finally:
            os.unlink(tmp_path)

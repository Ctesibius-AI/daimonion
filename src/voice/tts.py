"""
Kokoro TTS Module — text to speech via Kokoro-82M.

Voice: bf_isabella (British female)
Sample rate: 24000 Hz

Usage:
    tts = KokoroTTS()
    wav_bytes = tts.synthesize("Hello world")

If Kokoro is not installed, provides a stub that returns empty bytes.
"""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
import time

logger = logging.getLogger('daimonion.tts')

# Optional heavy dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None  # type: ignore[assignment]
    SOUNDFILE_AVAILABLE = False

try:
    from kokoro import KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    KPipeline = None  # type: ignore[misc,assignment]
    KOKORO_AVAILABLE = False

KOKORO_VOICE = 'bf_isabella'
KOKORO_LANG = 'b'  # British English
KOKORO_SAMPLE_RATE = 24000
KOKORO_REPO_ID = 'hexgrad/Kokoro-82M'


class KokoroTTS:
    """Text-to-speech via Kokoro-82M.

    Lazy-loads the model on first use. If Kokoro is not installed,
    all methods return empty bytes gracefully.
    """

    def __init__(
        self,
        voice: str = KOKORO_VOICE,
        lang: str = KOKORO_LANG,
        sample_rate: int = KOKORO_SAMPLE_RATE,
    ):
        self.voice = voice
        self.lang = lang
        self.sample_rate = sample_rate
        self._pipeline = None
        self._available = KOKORO_AVAILABLE and NUMPY_AVAILABLE and SOUNDFILE_AVAILABLE

    @property
    def available(self) -> bool:
        """Whether TTS dependencies are installed."""
        return self._available

    def _get_pipeline(self):
        """Lazy-load the Kokoro pipeline."""
        if self._pipeline is None:
            if not KOKORO_AVAILABLE:
                logger.warning('Kokoro not installed — TTS will return empty audio')
                return None
            logger.info('Loading Kokoro model...')
            t = time.time()
            self._pipeline = KPipeline(lang_code=self.lang, repo_id=KOKORO_REPO_ID)
            logger.info('Kokoro loaded in %.1fs', time.time() - t)
        return self._pipeline

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio bytes.

        Args:
            text: Text to synthesize.

        Returns:
            WAV audio bytes. Empty bytes if Kokoro is not available
            or synthesis fails.
        """
        if not self._available:
            logger.debug('TTS unavailable, returning empty bytes')
            return b''

        pipeline = self._get_pipeline()
        if pipeline is None:
            return b''

        t = time.time()
        try:
            all_audio = []
            for _gs, _ps, audio in pipeline(text, voice=self.voice):
                all_audio.append(audio)

            if not all_audio:
                return b''

            combined = np.concatenate(all_audio)

            buf = io.BytesIO()
            sf.write(buf, combined, self.sample_rate, format='WAV')
            wav_bytes = buf.getvalue()

            elapsed = time.time() - t
            logger.info('Synthesized %d chars in %.1fs (%d bytes)',
                        len(text), elapsed, len(wav_bytes))
            return wav_bytes

        except Exception as e:
            logger.error('TTS synthesis failed: %s', e, exc_info=True)
            return b''

    def synthesize_opus(self, text: str) -> bytes:
        """Synthesize text to Opus/OGG bytes (Telegram voice-note compatible).

        Requires ffmpeg to be installed.

        Args:
            text: Text to synthesize.

        Returns:
            OGG/Opus audio bytes. Empty bytes on failure.
        """
        wav_bytes = self.synthesize(text)
        if not wav_bytes:
            return b''

        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_f:
                wav_f.write(wav_bytes)
                wav_path = wav_f.name

            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as ogg_f:
                ogg_path = ogg_f.name

            subprocess.run([
                'ffmpeg', '-y', '-i', wav_path,
                '-c:a', 'libopus', '-b:a', '64k', '-ar', '48000',
                '-application', 'voip',
                ogg_path,
            ], capture_output=True, check=True)

            with open(ogg_path, 'rb') as f:
                opus_bytes = f.read()

            return opus_bytes

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error('Opus encoding failed (ffmpeg available?): %s', e)
            return b''
        finally:
            import os
            for p in (wav_path, ogg_path):
                try:
                    os.unlink(p)
                except (OSError, UnboundLocalError):
                    pass

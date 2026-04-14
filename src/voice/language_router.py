"""
Language Router — Detect language and route to the correct TTS engine.

English → Kokoro TTS (bf_isabella)
Greek   → GreekTTS-1.5 (Orpheus + SNAC)
Mixed   → Split by language, synthesize each part, concatenate

Detection uses Unicode character ranges — fast, no model needed.
"""

from __future__ import annotations

import io
import logging
import re
import struct

logger = logging.getLogger('daimonion.language_router')

# Greek Unicode ranges
GREEK_RANGE = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
# Latin/ASCII range (English indicator)
LATIN_RANGE = re.compile(r'[a-zA-Z]')


def detect_language(text: str) -> str:
    """Detect whether text is primarily Greek or English.

    Returns: 'greek', 'english', or 'mixed'
    """
    greek_count = len(GREEK_RANGE.findall(text))
    latin_count = len(LATIN_RANGE.findall(text))
    total = greek_count + latin_count

    if total == 0:
        return 'english'  # default for numbers, punctuation, etc.

    greek_ratio = greek_count / total
    if greek_ratio > 0.7:
        return 'greek'
    elif greek_ratio < 0.3:
        return 'english'
    return 'mixed'


def split_by_language(text: str) -> list[tuple[str, str]]:
    """Split text into segments by language.

    Returns: list of (segment_text, language) tuples.
    Consecutive same-language segments are merged.
    """
    segments = []
    current_lang = None
    current_chars = []

    for char in text:
        if GREEK_RANGE.match(char):
            char_lang = 'greek'
        elif LATIN_RANGE.match(char):
            char_lang = 'english'
        else:
            # Punctuation, numbers, spaces — keep with current language
            char_lang = current_lang or 'english'

        if char_lang != current_lang and current_chars:
            segments.append((''.join(current_chars), current_lang or 'english'))
            current_chars = []

        current_lang = char_lang
        current_chars.append(char)

    if current_chars:
        segments.append((''.join(current_chars), current_lang or 'english'))

    # Merge very short segments with neighbors
    merged = []
    for text_seg, lang in segments:
        if merged and lang == merged[-1][1]:
            merged[-1] = (merged[-1][0] + text_seg, lang)
        elif len(text_seg.strip()) < 3 and merged:
            # Very short segment — attach to previous
            merged[-1] = (merged[-1][0] + text_seg, merged[-1][1])
        else:
            merged.append((text_seg, lang))

    return merged


class VoiceRouter:
    """Routes text to the appropriate TTS engine based on language.

    English → KokoroTTS
    Greek → GreekTTS
    Mixed → Split, synthesize each, concatenate
    """

    def __init__(self, kokoro_tts=None, greek_tts=None):
        self._kokoro = kokoro_tts
        self._greek = greek_tts

    @property
    def kokoro(self):
        if self._kokoro is None:
            from src.voice.tts import KokoroTTS
            self._kokoro = KokoroTTS()
        return self._kokoro

    @property
    def greek(self):
        if self._greek is None:
            from src.voice.greek_tts import GreekTTS
            self._greek = GreekTTS()
        return self._greek

    @property
    def greek_available(self) -> bool:
        return self.greek.available and self.greek.models_downloaded

    @property
    def english_available(self) -> bool:
        return self.kokoro.available

    def synthesize(self, text: str) -> bytes:
        """Synthesize text using the appropriate TTS engine.

        Auto-detects language. For mixed text, splits and concatenates.

        Returns: WAV audio bytes.
        """
        lang = detect_language(text)

        if lang == 'english':
            return self._synthesize_english(text)
        elif lang == 'greek':
            return self._synthesize_greek(text)
        else:
            return self._synthesize_mixed(text)

    def _synthesize_english(self, text: str) -> bytes:
        if not self.english_available:
            logger.warning('Kokoro not available for English TTS')
            return b''
        return self.kokoro.synthesize(text)

    def _synthesize_greek(self, text: str) -> bytes:
        if not self.greek_available:
            logger.warning('GreekTTS not available — falling back to English TTS')
            return self._synthesize_english(text)
        return self.greek.synthesize(text)

    def _synthesize_mixed(self, text: str) -> bytes:
        """Split mixed-language text and synthesize each part."""
        segments = split_by_language(text)
        audio_parts = []

        for segment_text, lang in segments:
            segment_text = segment_text.strip()
            if not segment_text:
                continue

            if lang == 'greek' and self.greek_available:
                wav = self.greek.synthesize(segment_text)
            else:
                wav = self._synthesize_english(segment_text)

            if wav:
                audio_parts.append(wav)

        if not audio_parts:
            return b''

        if len(audio_parts) == 1:
            return audio_parts[0]

        return _concatenate_wav(audio_parts)


def _concatenate_wav(wav_parts: list[bytes]) -> bytes:
    """Concatenate multiple WAV files into one.

    Assumes all parts have the same format (mono, 16-bit, 24kHz).
    """
    all_data = []
    sample_rate = 24000

    for wav in wav_parts:
        if len(wav) < 44:
            continue
        # Skip WAV header (44 bytes), extract raw PCM data
        all_data.append(wav[44:])

    if not all_data:
        return b''

    combined = b''.join(all_data)
    data_size = len(combined)

    # Write new WAV header
    buf = io.BytesIO()
    buf.write(b'RIFF')
    buf.write(struct.pack('<I', 36 + data_size))
    buf.write(b'WAVE')
    buf.write(b'fmt ')
    buf.write(struct.pack('<I', 16))
    buf.write(struct.pack('<H', 1))        # PCM
    buf.write(struct.pack('<H', 1))        # mono
    buf.write(struct.pack('<I', sample_rate))
    buf.write(struct.pack('<I', sample_rate * 2))
    buf.write(struct.pack('<H', 2))        # block align
    buf.write(struct.pack('<H', 16))       # bits per sample
    buf.write(b'data')
    buf.write(struct.pack('<I', data_size))
    buf.write(combined)

    return buf.getvalue()

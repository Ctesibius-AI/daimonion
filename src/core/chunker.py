"""
Sentence-boundary chunker for streaming responses.

Buffers streaming text from Claude and yields complete sentence groups
suitable for TTS or incremental display. Chunk size is shaped by
confidence band:

  - lightning (>90%):   full response as one chunk (it's short anyway)
  - breathing (30-90%): 2-3 sentences per chunk
  - exploration (<30%): 1 sentence first chunk (the clarifying question),
                        then 2-3 sentences

Usage:
    chunker = SentenceChunker(confidence_band="breathing")
    for token in stream.text_stream:
        chunks = chunker.feed(token)
        for chunk in chunks:
            send_to_tts(chunk)
    # Flush remaining text at end of stream
    final = chunker.flush()
    if final:
        send_to_tts(final)
"""

import re

# Sentence-ending punctuation followed by space, newline, or end of string.
# Handles common abbreviations to avoid false splits.
_ABBREVIATIONS = {
    'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'sr.', 'jr.',
    'vs.', 'etc.', 'approx.', 'e.g.', 'i.e.', 'no.', 'vol.',
    'a.p.i.', 'u.s.', 'u.k.', 'e.u.',
}

_SENTENCE_END = re.compile(r'([.!?])\s')


class SentenceChunker:
    """Buffer streaming text and yield sentence-group chunks."""

    def __init__(self, confidence_band: str = 'breathing'):
        self.confidence_band = confidence_band
        self._buffer = ''
        self._sentences: list[str] = []
        self._chunks_emitted = 0

    @property
    def _target_sentences(self) -> int:
        """How many sentences to group per chunk."""
        if self.confidence_band == 'lightning':
            # Short answers — let them accumulate, flush at end
            return 99
        if self.confidence_band == 'exploration':
            # First chunk should be just the clarifying question
            if self._chunks_emitted == 0:
                return 1
            return 2
        # breathing — default
        return 2

    def feed(self, token: str) -> list[str]:
        """Feed a streaming token. Returns list of ready chunks (usually 0 or 1)."""
        self._buffer += token
        return self._try_extract()

    def flush(self) -> str | None:
        """Flush any remaining buffered text. Call at end of stream."""
        # Any complete sentences waiting
        remaining = self._buffer.strip()
        if remaining:
            self._sentences.append(remaining)
            self._buffer = ''

        if self._sentences:
            chunk = ' '.join(self._sentences)
            self._sentences.clear()
            self._chunks_emitted += 1
            return chunk
        return None

    def _try_extract(self) -> list[str]:
        """Try to extract complete sentences from the buffer."""
        chunks = []

        while True:
            match = _SENTENCE_END.search(self._buffer)
            if not match:
                break

            end_pos = match.end()
            candidate = self._buffer[:end_pos].strip()

            # Check for false splits on abbreviations
            if self._is_abbreviation(candidate):
                # Not a real sentence end — need more text.
                # But only if there's no further sentence end after this one.
                next_match = _SENTENCE_END.search(self._buffer, end_pos)
                if not next_match:
                    break
                # There's another sentence end — take up to that one instead
                end_pos = next_match.end()
                candidate = self._buffer[:end_pos].strip()

            self._sentences.append(candidate)
            self._buffer = self._buffer[end_pos:]

            if len(self._sentences) >= self._target_sentences:
                chunk = ' '.join(self._sentences)
                self._sentences.clear()
                self._chunks_emitted += 1
                chunks.append(chunk)

        return chunks

    def _is_abbreviation(self, text: str) -> bool:
        """Check if the text ends with a known abbreviation, not a sentence."""
        lower = text.lower()
        for abbr in _ABBREVIATIONS:
            if lower.endswith(abbr):
                return True
        return False

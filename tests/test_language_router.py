"""
Unit tests for the language router.

Tests language detection and text splitting. No models loaded.
"""

import pytest

from src.voice.language_router import detect_language, split_by_language


class TestDetectLanguage:
    def test_pure_english(self):
        assert detect_language('Hello world') == 'english'

    def test_pure_greek(self):
        assert detect_language('Καλημέρα κόσμε') == 'greek'

    def test_mixed(self):
        assert detect_language('Hello Καλημέρα world κόσμε') == 'mixed'

    def test_mostly_greek(self):
        assert detect_language('Σήμερα είναι μια ωραία day') == 'greek'

    def test_mostly_english(self):
        assert detect_language('Today is a beautiful μέρα') == 'english'

    def test_numbers_only(self):
        assert detect_language('12345') == 'english'

    def test_empty(self):
        assert detect_language('') == 'english'

    def test_punctuation_only(self):
        assert detect_language('!!! ???') == 'english'

    def test_greek_with_punctuation(self):
        assert detect_language('Πώς είσαι;') == 'greek'


class TestSplitByLanguage:
    def test_pure_english(self):
        result = split_by_language('Hello world')
        assert len(result) == 1
        assert result[0][1] == 'english'

    def test_pure_greek(self):
        result = split_by_language('Καλημέρα κόσμε')
        assert len(result) == 1
        assert result[0][1] == 'greek'

    def test_mixed_splits(self):
        result = split_by_language('Hello Καλημέρα')
        assert len(result) == 2
        assert result[0][1] == 'english'
        assert result[1][1] == 'greek'

    def test_preserves_text(self):
        text = 'Hello Καλημέρα world'
        result = split_by_language(text)
        combined = ''.join(seg for seg, _ in result)
        assert combined == text

    def test_short_segments_merged(self):
        # Very short segments should be merged with neighbors
        result = split_by_language('Καλημέρα a φίλε')
        # The single 'a' should be absorbed into surrounding Greek
        total_segments = len(result)
        assert total_segments <= 2  # should merge rather than create 3

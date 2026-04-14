#!/usr/bin/env python3
"""
Test Greek TTS — Generate sample audio files for evaluation.

Produces WAV files in ~/.daimonion/voice_tests/ for manual listening.
Tests: simple Greek, complex Greek, mixed Greek/English, English baseline.
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TESTS_DIR = os.path.expanduser('~/.daimonion/voice_tests')
os.makedirs(TESTS_DIR, exist_ok=True)

SAMPLES = [
    ('01_simple_greek', 'Καλημέρα, πώς είσαι;'),
    ('02_socrates', 'Ο Σωκράτης πίστευε ότι η αληθινή σοφία αρχίζει με την αναγνώριση της άγνοιας.'),
    ('03_pythia_intro', 'Είμαι η Πυθία. Σύντροφος στην αναζήτηση της αλήθειας.'),
    ('04_mixed', 'Η Pythia είναι ένα AI thinking partner.'),
    ('05_weather', 'Σήμερα στη Χαλκίδα έχει ηλιοφάνεια και είκοσι δύο βαθμούς.'),
]


def test_greek_tts():
    """Test GreekTTS directly."""
    from src.voice.greek_tts import GreekTTS

    tts = GreekTTS()
    print(f'GreekTTS available: {tts.available}')
    print(f'Models downloaded: {tts.models_downloaded}')

    if not tts.available:
        print('Dependencies missing. Install: torch, snac, llama-cpp-python')
        return

    if not tts.models_downloaded:
        print('Models not downloaded. Run: python -c "from src.voice.greek_tts import download_models; download_models()"')
        return

    print(f'\nGenerating {len(SAMPLES)} samples to {TESTS_DIR}/\n')

    for filename, text in SAMPLES:
        print(f'  {filename}: "{text[:50]}..."')
        t = time.time()
        wav = tts.synthesize(text)
        elapsed = time.time() - t

        if wav:
            path = os.path.join(TESTS_DIR, f'{filename}.wav')
            with open(path, 'wb') as f:
                f.write(wav)
            print(f'    OK: {len(wav):,} bytes, {elapsed:.1f}s → {path}')
        else:
            print(f'    FAILED: no audio generated ({elapsed:.1f}s)')

    print(f'\nDone. Listen to files in: {TESTS_DIR}/')
    print(f'  open {TESTS_DIR}/')


def test_language_router():
    """Test the language router (routes Greek vs English)."""
    from src.voice.language_router import VoiceRouter, detect_language

    router = VoiceRouter()
    print(f'\nLanguage Router:')
    print(f'  English (Kokoro): {router.english_available}')
    print(f'  Greek (GreekTTS): {router.greek_available}')

    if not router.greek_available:
        print('  Greek TTS not ready — skipping router test')
        return

    test_texts = [
        ('router_english', 'Good morning. How are you today?'),
        ('router_greek', 'Καλημέρα. Τι κάνεις σήμερα;'),
        ('router_mixed', 'Hello Καλημέρα, let us think together σήμερα.'),
    ]

    for filename, text in test_texts:
        lang = detect_language(text)
        print(f'\n  {filename} (detected: {lang}): "{text[:50]}..."')
        t = time.time()
        wav = router.synthesize(text)
        elapsed = time.time() - t

        if wav:
            path = os.path.join(TESTS_DIR, f'{filename}.wav')
            with open(path, 'wb') as f:
                f.write(wav)
            print(f'    OK: {len(wav):,} bytes, {elapsed:.1f}s')
        else:
            print(f'    FAILED ({elapsed:.1f}s)')


if __name__ == '__main__':
    print('=== Daimonion Greek Voice Test ===\n')
    test_greek_tts()
    # test_language_router()  # uncomment when Kokoro is also installed
    print('\n=== Done ===')

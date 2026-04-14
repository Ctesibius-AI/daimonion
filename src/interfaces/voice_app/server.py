"""
Pythia Voice App — Standalone local voice interface.

Tap to talk → Whisper STT → Pipeline → Kokoro TTS → hear response.

Runs as a local web server. Open http://localhost:8787 in browser.
Works with AirPods or any mic/speaker.

Usage:
    cd ~/daimonion
    .venv/bin/python -m src.interfaces.voice_app.server
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import tempfile
import time

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

sys.path.insert(0, os.path.expanduser('~/daimonion'))

from src.config import SONNET_MODEL, OPUS_MODEL
from src.core.conversation import Conversation
from src.tools.usage_tracker import tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('daimonion.voice_app')

app = FastAPI(title='Pythia Voice')

# ── State ──────────────────────────────────────────────────────────
conversation = Conversation('voice_app')
pipeline = None
whisper_model = None
tts_engine = None


def get_whisper():
    """Lazy-load Whisper model."""
    global whisper_model
    if whisper_model is None:
        logger.info('Loading Whisper base model...')
        t = time.time()
        import whisper
        whisper_model = whisper.load_model('base')
        logger.info('Whisper loaded in %.1fs', time.time() - t)
    return whisper_model


def get_tts():
    """Lazy-load TTS engine."""
    global tts_engine
    if tts_engine is None:
        try:
            from src.voice.tts import KokoroTTS
            tts_engine = KokoroTTS()
            if tts_engine.available:
                logger.info('Kokoro TTS available')
            else:
                logger.info('Kokoro TTS not available — responses will be text only')
                tts_engine = None
        except Exception:
            logger.info('TTS not available')
            tts_engine = None
    return tts_engine


def get_pipeline():
    """Lazy-load the pipeline (needs API key)."""
    global pipeline
    if pipeline is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key or len(api_key) < 10:
            logger.warning('No ANTHROPIC_API_KEY — pipeline unavailable, using echo mode')
            return None
        try:
            from src.core.pipeline import PythiaPipeline
            from src.memory.retrieval import create_retriever
            retriever = None
            try:
                retriever = create_retriever()
            except Exception:
                pass
            pipeline = PythiaPipeline(retriever=retriever, api_key=api_key)
            logger.info('Pipeline loaded')
        except Exception as e:
            logger.error('Pipeline failed: %s', e)
            return None
    return pipeline


# ── Routes ─────────────────────────────────────────────────────────

@app.get('/', response_class=HTMLResponse)
async def index():
    """Serve the voice app UI."""
    html_path = os.path.join(os.path.dirname(__file__), 'index.html')
    with open(html_path) as f:
        return f.read()


@app.post('/transcribe')
async def transcribe(audio: UploadFile = File(...)):
    """Receive audio, transcribe with Whisper."""
    t0 = time.time()

    # Save uploaded audio to temp file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model = get_whisper()
        result = model.transcribe(tmp_path, language=None)  # auto-detect language
        text = result['text'].strip()
        language = result.get('language', 'en')
        elapsed = time.time() - t0

        logger.info('Transcribed: "%s" [%s, %.1fs]', text[:80], language, elapsed)

        return {
            'text': text,
            'language': language,
            'elapsed_ms': int(elapsed * 1000),
        }
    finally:
        os.unlink(tmp_path)


@app.post('/respond')
async def respond(data: dict):
    """Process text through pipeline, return response + optional audio."""
    text = data.get('text', '').strip()
    if not text:
        return {'response': '', 'audio': False}

    t0 = time.time()

    # Add to conversation log
    conversation.add_user_message(text, source='voice')

    # Process through pipeline
    pipe = get_pipeline()
    if pipe:
        result = await pipe.process(conversation, interface='voice')
        response_text = result.get('response', '')
        model_used = result.get('model', '?')
        tools = [tc['tool'] for tc in result.get('tool_calls', [])]
    else:
        # Echo mode (no API key)
        response_text = f'[No API key — echo mode] You said: {text}'
        model_used = 'echo'
        tools = []
        conversation.add_assistant_message(response_text)

    elapsed = time.time() - t0

    # Generate TTS audio
    audio_b64 = None
    tts = get_tts()
    if tts and response_text:
        t_tts = time.time()
        wav_bytes = tts.synthesize(response_text)
        if wav_bytes:
            import base64
            audio_b64 = base64.b64encode(wav_bytes).decode('ascii')
            logger.info('TTS: %.1fs, %d bytes', time.time() - t_tts, len(wav_bytes))

    logger.info('Response: %s, %.1fs, tools=%s', model_used, elapsed, tools or 'none')

    return {
        'response': response_text,
        'model': model_used,
        'tools': tools,
        'elapsed_ms': int(elapsed * 1000),
        'audio': audio_b64,
    }


@app.get('/status')
async def status():
    """System status."""
    return {
        'conversation': conversation.get_context_summary(),
        'pipeline': 'active' if get_pipeline() else 'unavailable (no API key)',
        'whisper': 'loaded' if whisper_model else 'not loaded (lazy)',
        'tts': 'available' if get_tts() else 'unavailable',
        'usage': tracker.get_today_summary(),
    }


if __name__ == '__main__':
    print('\n  Pythia Voice App')
    print('  Open: http://localhost:8787\n')
    uvicorn.run(app, host='0.0.0.0', port=8787, log_level='info')

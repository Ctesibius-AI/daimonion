"""
Daimonion Telegram Bot — routes messages through PythiaPipeline.

Replaces the old classify -> select -> retrieve -> respond flow with:
- Continuous conversation log (file-backed, persistent)
- Sonnet as front desk with tools (search_memory, load_skill, escalate_to_opus)
- Opus called only for deep thinking
- Mandatory 1-second debounce on messages
- Voice message support (if whisper available)
- Every API call tracked via usage_tracker
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import GRAPH_DB_PATH
from src.core.conversation import Conversation
from src.tools.usage_tracker import tracker

# Pipeline — may not be built yet
try:
    from src.core.pipeline import PythiaPipeline
except ImportError:
    PythiaPipeline = None  # type: ignore[misc,assignment]

# Graphiti / retriever — optional
try:
    from graphiti_core import Graphiti
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.embedder.local import LocalEmbedder
    from graphiti_core.llm_client.anthropic_client import AnthropicClient
    from graphiti_core.llm_client.config import LLMConfig
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False

# Voice support — optional
try:
    from src.voice.pipeline import VoicePipeline
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

logger = logging.getLogger('daimonion.telegram')

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
AUTHORIZED_CHAT_ID = int(os.environ.get('TELEGRAM_CHAT_ID', '0'))
DEBOUNCE_SECONDS = 1.0


class DaimonionTelegramBot:
    """Telegram bot using conversation log + Sonnet/Opus pipeline."""

    def __init__(
        self,
        pipeline=None,
        authorized_chat_id: int | None = None,
    ):
        self.pipeline = pipeline
        self.authorized_chat_id = (
            authorized_chat_id if authorized_chat_id is not None else AUTHORIZED_CHAT_ID
        )
        self._conversations: dict[int, Conversation] = {}
        self._debounce_tasks: dict[int, asyncio.Task] = {}
        self._pending_updates: dict[int, Update] = {}
        self._voice_pipeline = None

    @property
    def voice_pipeline(self):
        """Lazy-load voice pipeline."""
        if self._voice_pipeline is None and VOICE_AVAILABLE:
            self._voice_pipeline = VoicePipeline()
        return self._voice_pipeline

    def _authorized(self, chat_id: int) -> bool:
        if self.authorized_chat_id == 0:
            return True
        return chat_id == self.authorized_chat_id

    def _get_conversation(self, chat_id: int) -> Conversation:
        """Get or create a conversation log for this chat."""
        if chat_id not in self._conversations:
            self._conversations[chat_id] = Conversation(session_id=str(chat_id))
        return self._conversations[chat_id]

    # -- Command Handlers ------------------------------------------------

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update.effective_chat.id):
            return
        await update.message.reply_text('Pythia is online. Send me a message.')

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update.effective_chat.id):
            return
        chat_id = update.effective_chat.id
        conv = self._get_conversation(chat_id)

        usage = tracker.get_today_summary()
        status = (
            f'Session: {conv.session_id}\n'
            f'Log: {conv.get_context_summary()}\n'
            f'Active skills: {", ".join(conv.active_skills) or "none"}\n'
            f'Today cost: ${usage.get("total_cost_usd", 0):.4f} ({usage.get("total_calls", 0)} calls)'
        )
        await update.message.reply_text(status)

    # -- Text Message Handler --------------------------------------------

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive a text message, add to conversation log, debounce, then respond."""
        chat_id = update.effective_chat.id
        if not self._authorized(chat_id):
            return

        message = update.message.text
        if not message:
            return

        # Add to conversation log immediately
        conv = self._get_conversation(chat_id)
        conv.add_user_message(message, source='telegram')
        logger.info('Message from %d: "%s" (%s)', chat_id, message[:60], conv.get_context_summary())

        # Store the latest update for reply
        self._pending_updates[chat_id] = update

        # Debounce -- reset timer on each new message
        if chat_id in self._debounce_tasks:
            self._debounce_tasks[chat_id].cancel()

        self._debounce_tasks[chat_id] = asyncio.create_task(
            self._debounced_respond(chat_id)
        )

    # -- Voice Message Handler -------------------------------------------

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages: download, transcribe, process."""
        chat_id = update.effective_chat.id
        if not self._authorized(chat_id):
            return

        vp = self.voice_pipeline
        if vp is None:
            await update.message.reply_text(
                'Voice is not available (whisper/soundfile not installed).'
            )
            return

        # Download voice file
        voice = update.message.voice or update.message.audio
        if not voice:
            return

        await update.effective_chat.send_action('typing')

        try:
            file = await context.bot.get_file(voice.file_id)
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name

            # Transcribe
            transcription, stt_time = vp.transcribe(tmp_path)
            logger.info('Voice transcription (%dms): "%s"', int(stt_time * 1000), transcription[:60])

            if not transcription:
                await update.message.reply_text('No speech detected.')
                return

            # Add to conversation log and process like text
            conv = self._get_conversation(chat_id)
            conv.add_user_message(transcription, source='voice')
            self._pending_updates[chat_id] = update

            # Process immediately (no debounce for voice)
            await self._respond(chat_id)

        except Exception as e:
            logger.error('Voice handling error: %s', e, exc_info=True)
            await update.message.reply_text('Failed to process voice message.')
        finally:
            try:
                os.unlink(tmp_path)
            except (OSError, UnboundLocalError):
                pass

    # -- Response Logic --------------------------------------------------

    async def _debounced_respond(self, chat_id: int):
        """Wait for debounce period, then respond to all accumulated messages."""
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return  # Another message arrived, timer reset

        await self._respond(chat_id)

    async def _respond(self, chat_id: int):
        """Process pending messages and send response."""
        update = self._pending_updates.pop(chat_id, None)
        if not update:
            return

        conv = self._get_conversation(chat_id)
        pending = conv.get_pending_user_text()
        if not pending:
            return

        # Show typing indicator
        await update.effective_chat.send_action('typing')

        if self.pipeline is None:
            await update.message.reply_text(
                'Pipeline not available. Please check configuration.'
            )
            return

        # Run the pipeline
        try:
            result = await self.pipeline.process(
                conversation=conv,
                interface='telegram',
            )

            response_text = result.get('response', '')
            if response_text:
                # Send response (chunk if long)
                await self._send_response(update, response_text)

                logger.info(
                    'Response: %dms, model=%s, tools=%s',
                    result.get('timing', {}).get('total_ms', 0),
                    result.get('model', '?'),
                    [tc['tool'] for tc in result.get('tool_calls', [])] or 'none',
                )
            else:
                logger.warning('Empty response from pipeline')

        except Exception as e:
            logger.error('Pipeline error: %s', e, exc_info=True)
            await update.message.reply_text(
                "Something went wrong on my end. Try again in a moment."
            )

    async def _send_response(self, update: Update, text: str):
        """Send response, chunking if necessary for Telegram's limit."""
        max_len = 4096  # Telegram message limit

        if len(text) <= max_len:
            await update.message.reply_text(text)
        else:
            # Split at sentence boundaries
            chunks = []
            current = ''
            for sentence in text.replace('. ', '.\n').split('\n'):
                if len(current) + len(sentence) + 1 > max_len:
                    chunks.append(current.strip())
                    current = sentence
                else:
                    current += ' ' + sentence if current else sentence
            if current.strip():
                chunks.append(current.strip())

            for chunk in chunks:
                await update.message.reply_text(chunk)
                await asyncio.sleep(0.3)

    def build_application(self) -> Application:
        """Build the telegram Application with all handlers."""
        app = Application.builder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler('start', self.handle_start))
        app.add_handler(CommandHandler('status', self.handle_status))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message,
        ))
        app.add_handler(MessageHandler(
            filters.VOICE | filters.AUDIO,
            self.handle_voice,
        ))

        return app


async def main():
    """Start the Daimonion Telegram bot."""
    logging.basicConfig(
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        level=logging.INFO,
    )

    # Initialize Graphiti retriever (optional)
    retriever = None
    if GRAPHITI_AVAILABLE:
        try:
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'

            driver = KuzuDriver(db=GRAPH_DB_PATH)
            llm = AnthropicClient(config=LLMConfig(model='claude-haiku-4-5-20251001'))
            embedder = LocalEmbedder()
            graphiti = Graphiti(graph_driver=driver, llm_client=llm, embedder=embedder)
            await graphiti.build_indices_and_constraints()

            # Retriever — try to import from memory module
            try:
                from src.memory.retrieval import ThreeModeRetriever
                retriever = ThreeModeRetriever(graphiti, group_id='daimonion')
            except ImportError:
                logger.warning('ThreeModeRetriever not available')

            logger.info('Graphiti retriever initialized')
        except Exception as e:
            logger.warning('Graphiti init failed (memory search unavailable): %s', e)

    # Build pipeline
    pipeline = None
    if PythiaPipeline is not None:
        pipeline = PythiaPipeline(retriever=retriever)
    else:
        logger.warning('PythiaPipeline not available — bot will run without processing')

    # Build and run bot
    bot = DaimonionTelegramBot(pipeline=pipeline)
    app = bot.build_application()

    logger.info('Daimonion Telegram bot starting...')
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Run until interrupted
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == '__main__':
    asyncio.run(main())

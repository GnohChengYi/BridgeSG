from telegram import Update
from telegram.ext import Application, CommandHandler
import logging
import os
from flask.cli import load_dotenv
from http import HTTPStatus
import asyncio

from typing import Optional
from handlers import COMMAND_HANDLERS, SUPPORTED_COMMANDS
from lobby import CALLBACK_HANDLERS
from inline_handlers import INLINE_HANDLERS

def extract_command_from_text(text: Optional[str]) -> Optional[str]:
    """Return the command name (without leading slash) if text contains a command.

    Only checks if the text starts with '/' and extracts the contiguous
    non-space token after it. Returns None if no command found.
    """
    if not text:
        return None
    s = text.strip()
    if not s.startswith("/"):
        return None
    # command may be like '/start' or '/start@BotName' or '/stop  ' etc.
    token = s.split()[0]
    token = token.split('@')[0]
    return token.lstrip('/')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load environment variables early
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")


def process_update_sync(update_json: dict):
    """Serverless-friendly synchronous processor for incoming update JSON.

    If the update contains a message with text '/start', build a short-lived
    Application, register the async handler and run the update in a fresh
    event loop so we can reuse the same handler logic.
    """
    # Fail fast if token isn't configured; no need to parse the update.
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN not configured, skipping processing")
        return (HTTPStatus.OK, "no token")

    try:
        # Check for message-based command first; callback_query updates
        # may carry the chat id inside callback_query.message.chat.
        message = update_json.get("message") or {}
        callback = update_json.get("callback_query") or {}
        inline_query = update_json.get("inline_query") or {}
        chosen_inline_result = update_json.get("chosen_inline_result") or {}
        text = message.get("text", "")

        # chat id may be in message.chat or callback_query.message.chat
        chat = message.get("chat") or (callback.get("message") or {}).get("chat") or {}
        chat_id = chat.get("id")

        # If incoming text includes a supported command, process it.
        cmd = extract_command_from_text(text)

        # Detect different update types
        is_callback = bool(callback)
        is_inline_query = bool(inline_query)
        is_chosen_inline_result = bool(chosen_inline_result)

        # For inline queries, we don't need chat_id (user-specific)
        # For other updates, we need chat_id
        if not (is_inline_query or is_chosen_inline_result) and not chat_id:
            return (HTTPStatus.OK, "no chat id")

        # If none of the supported update types, nothing to do
        if not ((cmd and cmd in SUPPORTED_COMMANDS) or is_callback or is_inline_query or is_chosen_inline_result):
            return (HTTPStatus.OK, "unsupported update")

        # We'll build a short-lived Application and register either the
        # requested command handler (for commands) and always register
        # callback handlers so callback_query updates are handled.
        try:
            if cmd:
                logger.info("Processing /%s (sync) for chat: %s", cmd, chat_id)
            if is_callback:
                logger.info("Processing callback_query (sync) for update_id: %s", update_json.get("update_id"))
            if is_inline_query:
                logger.info("Processing inline_query (sync) for user: %s", inline_query.get("from", {}).get("id"))
            if is_chosen_inline_result:
                logger.info("Processing chosen_inline_result (sync) for user: %s", chosen_inline_result.get("from", {}).get("id"))

            app = Application.builder().token(TELEGRAM_TOKEN).build()

            # Attach only the handler(s) we need for this update:
            # - command handler when a supported command was received
            # - callback handlers when this is a callback_query update
            # - inline handlers when this is an inline_query or chosen_inline_result update
            if cmd:
                handler_fn = COMMAND_HANDLERS.get(cmd)
                if handler_fn:
                    app.add_handler(CommandHandler(cmd, handler_fn))

            if is_callback:
                for h in CALLBACK_HANDLERS:
                    try:
                        app.add_handler(h)
                    except Exception:
                        logger.exception("Failed to add callback handler %s", getattr(h, '__name__', repr(h)))

            if is_inline_query or is_chosen_inline_result:
                for h in INLINE_HANDLERS:
                    try:
                        app.add_handler(h)
                    except Exception:
                        logger.exception("Failed to add inline handler %s", getattr(h, '__name__', repr(h)))

            update = Update.de_json(update_json, app.bot)

            async def _run_once():
                await app.initialize()
                await app.process_update(update)
                await app.shutdown()

            asyncio.run(_run_once())
        except Exception:
            logger.exception("Failed to run per-invocation Application")
            return (HTTPStatus.INTERNAL_SERVER_ERROR, "app error")

    except Exception:
        logger.exception("Error processing update sync")
    return (HTTPStatus.OK, "ok")

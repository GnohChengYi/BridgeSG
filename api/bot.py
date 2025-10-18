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
        text = message.get("text", "")

        # chat id may be in message.chat or callback_query.message.chat
        chat = message.get("chat") or (callback.get("message") or {}).get("chat") or {}
        chat_id = chat.get("id")

        # If incoming text includes a supported command, process it.
        cmd = extract_command_from_text(text)

        # Also support callback_query updates.
        is_callback = bool(callback)

        # If we don't have a chat id, bail early.
        if not chat_id:
            return (HTTPStatus.OK, "no chat id")

        # If neither a supported command nor a callback, nothing to do.
        if not ((cmd and cmd in SUPPORTED_COMMANDS) or is_callback):
            return (HTTPStatus.OK, "unsupported update")

        # We'll build a short-lived Application and register either the
        # requested command handler (for commands) and always register
        # callback handlers so callback_query updates are handled.
        try:
            if cmd:
                logger.info("Processing /%s (sync) for chat: %s", cmd, chat_id)
            if is_callback:
                logger.info("Processing callback_query (sync) for update_id: %s", update_json.get("update_id"))

            app = Application.builder().token(TELEGRAM_TOKEN).build()

            # Attach only the handler(s) we need for this update:
            # - command handler when a supported command was received
            # - callback handlers only when this is a callback_query update
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

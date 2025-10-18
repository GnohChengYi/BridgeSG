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
    try:
        message = update_json.get("message") or {}
        text = message.get("text", "")
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if not chat_id:
            return (HTTPStatus.OK, "no chat id")

        # If incoming text includes a supported command, process it.
        cmd = extract_command_from_text(text)
        # Only handle commands we explicitly support.
        if cmd and cmd in SUPPORTED_COMMANDS:
            logger.info("Processing /%s (sync) for chat: %s", cmd, chat_id)
            try:
                app = Application.builder().token(TELEGRAM_TOKEN).build()
                # Attach only the handler for the requested command
                handler_fn = COMMAND_HANDLERS.get(cmd)
                if handler_fn:
                    app.add_handler(CommandHandler(cmd, handler_fn))

                # Attach any callback handlers. Registering extra handlers on a
                # short-lived per-invocation Application is inexpensive and
                # avoids conditional logic here. Handlers will simply not be
                # invoked unless the update matches their filter.
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

from telegram import Update
from telegram.ext import Application, CommandHandler
import logging
import os
from flask.cli import load_dotenv
import redis
from datetime import datetime
from http import HTTPStatus
import asyncio

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


def _create_redis_client(url: str):
    """Return a redis client for the given URL, or None if not configured.

    This is small helper to centralize Redis construction and avoid raising
    on import when REDIS_URL is missing (serverless environments may not set it
    for some routes).
    """
    if not url:
        logger.warning("REDIS_URL not set; Redis features will be disabled")
        return None
    try:
        return redis.StrictRedis.from_url(url)
    except Exception:
        logger.exception("Failed to create Redis client from URL")
        return None


# Construct redis client (may be None if not configured)
redis_client = _create_redis_client(REDIS_URL)


def handle_start_for_chat():
    """Shared synchronous helper that updates Redis and returns reply text.

    The function intentionally keeps behavior synchronous so it can be reused
    from both sync serverless handlers and async CommandHandlers.
    """
    try:
        current_time = datetime.now().isoformat()
        if redis_client:
            redis_client.set("last_start_time", current_time)
            retrieved = redis_client.get("last_start_time")
            if retrieved:
                retrieved_time = retrieved.decode("utf-8")
            else:
                retrieved_time = current_time
        else:
            # Fallback: no Redis available
            retrieved_time = current_time
        return f"The last start time was: {retrieved_time}"
    except Exception:
        logger.exception("Error in handle_start_for_chat")
        return None


async def start(update: Update, context):
    """Async /start handler that reuses the sync helper for storage logic."""
    logger.info("Processing /start command from user: %s", update.effective_user)
    chat = update.effective_chat
    if chat and chat.id:
        reply_text = handle_start_for_chat()
        if reply_text:
            await update.message.reply_text(reply_text)


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

        if text and text.strip().startswith("/start"):
            logger.info("Processing /start (sync) for chat: %s", chat_id)
            try:
                app = Application.builder().token(TELEGRAM_TOKEN).build()
                app.add_handler(CommandHandler("start", start))

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


# Create the dummy bot application for local/long-running usage
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# Expose the application for linking
dummy_application = application

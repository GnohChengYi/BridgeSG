from telegram import Update
from telegram.ext import Application, CommandHandler
import logging
import os
from flask.cli import load_dotenv
import redis
from datetime import datetime
from http import HTTPStatus
import asyncio
import json

from bridge import Game

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


def _save_game_to_redis(chat_id: int, game: Game):
    """Serialize and save a Game instance to Redis (if available).

    The function is defensive: if Redis is not configured it logs a warning
    and returns False. It does not raise.
    """
    if not redis_client:
        logger.warning("Redis not configured; skipping game persistence for chat %s", chat_id)
        return False
    try:
        redis_client.set(f"game:{chat_id}", json.dumps(game.to_dict()))
        return True
    except Exception:
        logger.exception("Failed to save game to Redis for chat %s", chat_id)
        return False


def _game_exists_in_redis(chat_id: int) -> bool:
    """Return True if a saved game exists for chat_id in Redis."""
    if not redis_client:
        return False
    try:
        return redis_client.exists(f"game:{chat_id}") == 1
    except Exception:
        logger.exception("Error checking game existence in Redis for chat %s", chat_id)
        return False


async def start(update: Update, context):
    """Async /start handler that reuses the sync helper for storage logic."""
    logger.info("Processing /start command from user: %s", update.effective_user)
    chat = update.effective_chat
    if not (chat and chat.id):
        return

    chat_id = chat.id

    # If a game already exists for this chat, reuse the stored info and reply.
    if _game_exists_in_redis(chat_id):
        reply_text = handle_start_for_chat()
        if reply_text:
            await update.message.reply_text(f"A game already exists. {reply_text}")
        return

    # Create a new Game instance and persist it. Keep the Game creation
    # synchronous so it can be reused from different handlers (see old_bot.py / bot2.py).
    try:
        game = Game(str(chat_id))
        saved = _save_game_to_redis(chat_id, game)
        reply_text = handle_start_for_chat()
        if saved:
            resp = f"New game created for this chat (id={game.id}). {reply_text}"
        else:
            resp = f"New game created locally (id={game.id}) but Redis persistence is unavailable. {reply_text}"
        await update.message.reply_text(resp)
    except Exception:
        logger.exception("Failed to create and persist new game for chat %s", chat_id)
        await update.message.reply_text("Failed to start a new game. Please try again later.")


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

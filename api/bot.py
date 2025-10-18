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
    """Return a redis client or exit the process if Redis isn't available.

    Redis is required for correct operation in this project. Fail fast and
    loudly during import so misconfiguration is detected early.
    """
    if not url:
        logger.error("REDIS_URL not set; Redis is required.")
        raise SystemExit(1)
    try:
        client = redis.StrictRedis.from_url(url)
        # Verify connectivity early (raises on failure)
        client.ping()
        return client
    except Exception:
        logger.exception("Failed to create/connect to Redis at URL: %s", url)
        raise SystemExit(1)


# Construct redis client (will exit on failure)
redis_client = _create_redis_client(REDIS_URL)


def handle_start_for_chat():
    """Shared synchronous helper that updates Redis and returns reply text.

    The function intentionally keeps behavior synchronous so it can be reused
    from both sync serverless handlers and async CommandHandlers.
    """
    try:
        current_time = datetime.now().isoformat()
        # Redis is required; this should not fail silently. Use try/except
        redis_client.set("last_start_time", current_time)
        retrieved = redis_client.get("last_start_time")
        retrieved_time = retrieved.decode("utf-8") if retrieved else current_time
        return f"The last start time was: {retrieved_time}"
    except Exception:
        logger.exception("Error in handle_start_for_chat")
        return None


def _save_game_to_redis(chat_id: int, game: Game):
    """Serialize and save a Game instance to Redis (if available).

    The function is defensive: if Redis is not configured it logs a warning
    and returns False. It does not raise.
    """
    try:
        redis_client.set(f"game:{chat_id}", json.dumps(game.to_dict()))
        return True
    except Exception:
        logger.exception("Failed to save game to Redis for chat %s", chat_id)
        return False


def _game_exists_in_redis(chat_id: int) -> bool:
    """Return True if a saved game exists for chat_id in Redis."""
    try:
        return redis_client.exists(f"game:{chat_id}") == 1
    except Exception:
        logger.exception("Error checking game existence in Redis for chat %s", chat_id)
        return False


def _load_game_from_redis(chat_id: int):
    """Load a Game instance from Redis (or return None).

    Defensive: if Redis is unavailable or the stored data is malformed,
    log and return None.
    """
    try:
        data = redis_client.get(f"game:{chat_id}")
        if not data:
            return None
        return Game.from_dict(json.loads(data))
    except Exception:
        logger.exception("Failed to load game from Redis for chat %s", chat_id)
        return None


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
        # chat_id is an integer key used throughout
        game = Game(chat_id)
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


async def stop(update: Update, context):
    """Async /stop handler.

    Stops the persisted game for this chat (if any), removes Redis key,
    and clears the in-memory Player registry for players in the game.
    """
    logger.info("Processing /stop command from user: %s", update.effective_user)
    chat = update.effective_chat
    if not (chat and chat.id):
        return

    chat_id = chat.id

    game = _load_game_from_redis(chat_id)
    if not game:
        await update.message.reply_text("No game started!")
        return

    # Attempt to stop the game and delete persisted state.
    try:
        # Delete persisted state first
        try:
            redis_client.delete(f"game:{chat_id}")
        except Exception:
            logger.exception("Failed to delete game from Redis for chat %s", chat_id)

        # If there is an in-memory instance in this process, stop it too
        in_memory_game = Game.games.get(chat_id)
        if in_memory_game:
            try:
                in_memory_game.stop()
            except Exception:
                logger.exception("Error while stopping in-memory game for chat %s", chat_id)
    except Exception:
        logger.exception("Unexpected error while stopping game for chat %s", chat_id)

    # In serverless-only environment, in-memory registries are unlikely to be
    # populated. We attempted to stop any in-memory instance above; nothing
    # further to do here.

    await update.message.reply_text("Game stopped.")


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
                app.add_handler(CommandHandler("stop", stop))

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

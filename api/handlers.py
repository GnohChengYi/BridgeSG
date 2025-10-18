from telegram import Update
import logging
from bridge import Game

from store import (
    redis_client,
    handle_start_for_chat,
    save_game_to_redis,
    game_exists_in_redis,
    load_game_from_redis,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context):
    """Async /start handler that reuses the sync helper for storage logic."""
    logger.info("Processing /start command from user: %s", update.effective_user)
    chat = update.effective_chat
    if not (chat and chat.id):
        return

    chat_id = chat.id

    if game_exists_in_redis(redis_client, chat_id):
        reply_text = handle_start_for_chat(redis_client)
        if reply_text:
            await update.message.reply_text(f"A game already exists. {reply_text}")
        return

    try:
        game = Game(chat_id)
        saved = save_game_to_redis(redis_client, chat_id, game)
        reply_text = handle_start_for_chat(redis_client)
        if saved:
            resp = f"New game created for this chat (id={game.id}). {reply_text}"
        else:
            resp = f"New game created locally (id={game.id}) but Redis persistence is unavailable. {reply_text}"
        await update.message.reply_text(resp)
    except Exception:
        logger.exception("Failed to create and persist new game for chat %s", chat_id)
        await update.message.reply_text("Failed to start a new game. Please try again later.")


async def stop(update: Update, context):
    """Async /stop handler."""
    logger.info("Processing /stop command from user: %s", update.effective_user)
    chat = update.effective_chat
    if not (chat and chat.id):
        return

    chat_id = chat.id

    game = load_game_from_redis(redis_client, chat_id)
    if not game:
        await update.message.reply_text("No game started!")
        return

    try:
        try:
            redis_client.delete(f"game:{chat_id}")
        except Exception:
            logger.exception("Failed to delete game from Redis for chat %s", chat_id)

        in_memory_game = Game.games.get(chat_id)
        if in_memory_game:
            try:
                in_memory_game.stop()
            except Exception:
                logger.exception("Error while stopping in-memory game for chat %s", chat_id)
    except Exception:
        logger.exception("Unexpected error while stopping game for chat %s", chat_id)

    await update.message.reply_text("Game stopped.")


# Public mapping of command name -> handler callable. Kept here so the bot
# wiring can remain focused on parsing and registering handlers.
HANDLERS = {"start": start, "stop": stop}
SUPPORTED_COMMANDS = list(HANDLERS.keys())

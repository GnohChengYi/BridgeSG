from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import logging
from bridge import Game

from store import (
    redis_client,
    save_join_message,
    load_join_message,
    delete_join_message,
    save_game_to_redis,
    game_exists_in_redis,
    load_game_from_redis,
)
from lobby import get_markup

logger = logging.getLogger(__name__)


async def start(update: Update, context):
    """Async /start handler that reuses the sync helper for storage logic."""
    logger.info("Processing /start command from user: %s", update.effective_user)
    chat = update.effective_chat
    if not (chat and chat.id):
        return

    chat_id = chat.id

    if game_exists_in_redis(redis_client, chat_id):
        await update.message.reply_text(f"A game already exists.")
        return

    try:
        game = Game(chat_id)
        saved = save_game_to_redis(redis_client, chat_id, game)
        if saved:
            resp = "New game created for this chat."
            # send join inline keyboard
            sent = await update.message.reply_text(resp, reply_markup=get_markup())
        else:
            resp = "Game created but may not be saved properly. Try again another day."
            sent = await update.message.reply_text(resp)

        # persist the join message id so callback handler can reference it
        try:
            save_join_message(redis_client, chat_id, sent.message_id)
        except Exception:
            logger.exception("Failed to persist join message id for chat %s", chat_id)
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

    # TODO remove join_message reply markup (if any)
    try:
        # Clear stored join message reply_markup if present so the inline keyboard is removed
        try:
            join_msg_id = load_join_message(redis_client, chat_id)
            if join_msg_id:
                try:
                    # Use bot to edit message and remove reply_markup (set to None)
                    await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=join_msg_id, reply_markup=None)
                except Exception:
                    logger.exception("Failed to clear reply_markup for join message %s in chat %s", join_msg_id, chat_id)
                # delete stored join message id from redis
                try:
                    delete_join_message(redis_client, chat_id)
                except Exception:
                    logger.exception("Failed to delete stored join message id for chat %s", chat_id)

        except Exception:
            logger.exception("Failed while attempting to clear join message reply_markup for chat %s", chat_id)

        try:
            redis_client.delete(f"game:{chat_id}")
        except Exception:
            logger.exception("Failed to delete game from Redis for chat %s", chat_id)

        # No in-process registry used; Redis is canonical. Nothing else to do.
    except Exception:
        logger.exception("Unexpected error while stopping game for chat %s", chat_id)

    await update.message.reply_text("Game stopped.")


async def help(update: Update, context):
    """Async /help handler providing friendly update for bridge players."""
    logger.info("Processing /help command from user: %s", update.effective_user)
    message = """🃏 BridgeSG is getting a shiny upgrade! 🚀

We're moving to a modern setup to keep your games fast and reliable. Stay tuned for the latest updates!

Check out our GitHub repo for migration status: https://github.com/GnohChengYi/BridgeSG

Happy bridging! 🃏"""
    await update.message.reply_text(message, parse_mode='Markdown')


# Public mapping of command name -> handler callable. Kept here so the bot
# wiring can remain focused on parsing and registering handlers.
COMMAND_HANDLERS = {"start": start, "stop": stop, "help": help}
SUPPORTED_COMMANDS = list(COMMAND_HANDLERS.keys())

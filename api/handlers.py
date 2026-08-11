from telegram import Update
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
    set_user_active_game,
)
from lobby import get_markup
from game_utils import translate_bid, request_bid_in_chat, parse_display_bid

logger = logging.getLogger(__name__)


async def start(update: Update, context):
    """Async /start handler that reuses the sync helper for storage logic."""
    logger.info("Processing /start command from user: %s", update.effective_user)
    chat = update.effective_chat
    if not (chat and chat.id):
        return

    chat_id = chat.id
    user_id = update.effective_user.id

    # Record this user's active chat for inline query context
    set_user_active_game(redis_client, user_id, chat_id)

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
    user_id = update.effective_user.id

    # Record this user's active chat for inline query context
    set_user_active_game(redis_client, user_id, chat_id)

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
    chat = update.effective_chat
    if chat and chat.id:
        user_id = update.effective_user.id
        # Record this user's active chat for inline query context
        set_user_active_game(redis_client, user_id, chat.id)

    message = """🃏 BridgeSG is getting a shiny upgrade! 🚀

We're moving to a modern setup to keep your games fast and reliable. Stay tuned for the latest updates!

Check out our GitHub repo for migration status: https://github.com/GnohChengYi/BridgeSG

Happy bridging! 🃏"""
    await update.message.reply_text(message, parse_mode='Markdown')


async def handle_text_message(update: Update, context):
    """Handle plain text bid entries from chat participants."""
    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text.strip() if update.message and update.message.text else ''

    logger.info("Received plain text from user %s in chat %s: %s", user.id if user else None, chat.id if chat else None, text)

    if not chat or not chat.id or not user or not user.id:
        return

    game = load_game_from_redis(redis_client, chat.id)
    if not game:
        return

    player = next((p for p in game.players if p.id == user.id), None)
    if not player or player is not game.activePlayer:
        return

    if game.phase != Game.BID_PHASE:
        return

    bid_text = parse_display_bid(text)
    if not bid_text:
        logger.info("Ignoring unparseable bid text from user %s: %s", user.id, text)
        return

    if bid_text != Game.PASS and bid_text not in game.valid_bids():
        logger.info("Ignoring invalid bid text from user %s: %s", user.id, bid_text)
        return

    logger.info("Processing plain text bid from user %s in chat %s: %s", user.id, chat.id, bid_text)
    if not player.make_bid(bid_text):
        logger.warning("make_bid rejected plain text bid for user %s in chat %s: %s", user.id, chat.id, bid_text)
        await update.message.reply_text('Invalid bid or not your turn.')
        return

    save_game_to_redis(redis_client, chat.id, game)
    await update.message.reply_text(f'{player.name}: {translate_bid(bid_text)}')

    if getattr(game.activePlayer, 'isAI', False):
        await request_bid_in_chat(context.bot, game, chat.id)
        save_game_to_redis(redis_client, chat.id, game)


# Public mapping of command name -> handler callable. Kept here so the bot
# wiring can remain focused on parsing and registering handlers.
COMMAND_HANDLERS = {"start": start, "stop": stop, "help": help}
SUPPORTED_COMMANDS = list(COMMAND_HANDLERS.keys())

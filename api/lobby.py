from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import logging
from bridge import Game

from store import (
    redis_client,
    save_game_to_redis,
    load_game_from_redis,
    load_join_message,
)

logger = logging.getLogger(__name__)


# Action constants for callback_data
ACTION_JOIN = "join"
ACTION_QUIT = "quit"
ACTION_INSERT_AI = "insert_ai"
ACTION_DELETE_AI = "delete_ai"


def get_markup():
    first_row = [InlineKeyboardButton("Join!", callback_data=ACTION_JOIN),
                 InlineKeyboardButton("Quit...", callback_data=ACTION_QUIT)]
    second_row = [InlineKeyboardButton("Insert AI", callback_data=ACTION_INSERT_AI),
                  InlineKeyboardButton("Delete AI", callback_data=ACTION_DELETE_AI)]
    return InlineKeyboardMarkup([first_row, second_row])


def _build_join_text(game: Game) -> str:
    """Return the join message text for the provided game."""
    text = "Waiting for players to join ...\nJoined players:\n"
    text += "\n".join([p.name for p in game.players])
    return text


async def _safe_edit_join_message(bot, chat_id: int, message_id: int, text: str, reply_markup):
    """Try to edit the join message; log but don't raise on failure."""
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup)
    except Exception:
        logger.exception("Failed to edit join message for chat %s", chat_id)


async def lobby_callback_handler(update, context):
    """Handle inline keyboard presses for lobby (join/quit/insert/delete)."""
    q = update.callback_query
    await q.answer()
    data = q.data
    chat = q.message.chat
    chat_id = chat.id

    # Load game and join_message id
    game = load_game_from_redis(redis_client, chat_id)
    join_msg_id = load_join_message(redis_client, chat_id)

    # Safe fallback: if no game, inform user
    if not game:
        await q.message.reply_text("No game started in this chat. Use /start to begin.")
        return

    # map each action to a small handler that returns (success: bool, message_on_failure: Optional[str])
    def _do_join():
        user = q.from_user
        ok = game.add_human(user.id, user.first_name)
        return ok, "Could not join the game (it may be full or you are already in a game)."

    def _do_quit():
        user = q.from_user
        ok = game.del_human(user.id)
        return ok, "You are not in the game of this chat!"

    def _do_insert_ai():
        ok = game.add_AI()
        return ok, "Game is full; cannot insert AI."

    def _do_delete_ai():
        ok = game.del_AI()
        return ok, "No AI in the game!"

    actions = {
        ACTION_JOIN: _do_join,
        ACTION_QUIT: _do_quit,
        ACTION_INSERT_AI: _do_insert_ai,
        ACTION_DELETE_AI: _do_delete_ai,
    }

    handler = actions.get(data)
    if not handler:
        await q.message.reply_text("Unknown action")
        return

    ok, fail_msg = handler()
    if not ok:
        await q.message.reply_text(fail_msg)
        return

    # success -> persist updated game and update join message text
    save_game_to_redis(redis_client, chat_id, game)
    text = _build_join_text(game)
    if join_msg_id:
        await _safe_edit_join_message(context.bot, chat_id, join_msg_id, text, q.message.reply_markup)

# Export callback handlers for wiring
CALLBACK_HANDLERS = [CallbackQueryHandler(lobby_callback_handler)]

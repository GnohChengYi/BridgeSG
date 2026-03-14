from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import InlineQueryHandler, ChosenInlineResultHandler
import logging

from bridge import Game
from store import (
    redis_client,
    find_game_by_active_player,
    save_game_to_redis,
    get_user_active_game,
    load_game_from_redis,
    set_user_active_game,
)
from game_utils import translate_bid, translate_card, thumb_url_bid, thumb_url_card, request_bid_in_chat

logger = logging.getLogger(__name__)


def _build_bid_results(game):
    """Build inline query results for BID_PHASE."""
    return [
        InlineQueryResultArticle(
            id=bid,
            title=translate_bid(bid),
            input_message_content=InputTextMessageContent(translate_bid(bid)),
            thumbnail_url=thumb_url_bid(bid)
        )
        for bid in game.valid_bids()
    ]


def _build_partner_results(player):
    """Build inline query results for CALL_PHASE (partner selection)."""
    # Show all cards NOT in declarer's hand
    return [
        InlineQueryResultArticle(
            id=card,
            title=translate_card(card),
            input_message_content=InputTextMessageContent(translate_card(card)),
            thumbnail_url=thumb_url_card(card)
        )
        for card in Game.deck if card not in player.hand
    ]


def _build_card_results(player):
    """Build inline query results for PLAY_PHASE."""
    return [
        InlineQueryResultArticle(
            id=card,
            title=translate_card(card),
            input_message_content=InputTextMessageContent(translate_card(card)),
            thumbnail_url=thumb_url_card(card)
        )
        for card in player.valid_cards()
    ]


async def inline_query_handler(update, context):
    """Handle inline queries for bid/partner/card selection.

    When a player types @BotName in chat, this handler shows them a dropdown
    of valid options based on the current game phase.

    Since inline_query payloads never include chat context, we use session-based
    routing: look up the user's active chat from Redis, then load the game from there.
    Falls back to scanning for active player if session lookup fails.
    """
    query = update.inline_query
    user_id = query.from_user.id

    # Primary: Try session-based lookup (user's most recent active chat)
    chat_id = get_user_active_game(redis_client, user_id)
    game = None

    if chat_id:
        game = load_game_from_redis(redis_client, chat_id)

    # Fallback: Scan for any game where this user is the active player
    if not game:
        chat_id, game = find_game_by_active_player(redis_client, user_id)

    if not game or not game.activePlayer or game.activePlayer.id != user_id:
        # User not in any active game or not their turn
        await query.answer([], cache_time=2, is_personal=True)
        return

    try:
        results = []
        if game.phase == Game.BID_PHASE:
            results = _build_bid_results(game)
        elif game.phase == Game.CALL_PHASE:
            results = _build_partner_results(game.activePlayer)
        elif game.phase == Game.PLAY_PHASE:
            results = _build_card_results(game.activePlayer)

        await query.answer(results, cache_time=2, is_personal=True)
    except Exception:
        logger.exception("Failed to build inline query results for user %s in chat %s", user_id, chat_id)
        await query.answer([], cache_time=2, is_personal=True)


async def _handle_bid_selection(player, selected_id, chat_id, context):
    """Process bid selection in BID_PHASE."""
    if not player.make_bid(selected_id):
        await context.bot.send_message(chat_id=chat_id, text='Not your turn or invalid bid!')
        return False
    return True


async def _handle_partner_selection(player, selected_id, chat_id, context):
    """Process partner card selection in CALL_PHASE."""
    if not player.call_partner(selected_id):
        await context.bot.send_message(chat_id=chat_id, text='Not your turn or invalid card!')
        return False
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f'Partner selected: {translate_card(selected_id)}\nPlay phase starting...'
    )
    return True


async def _handle_card_play(player, selected_id, chat_id, context):
    """Process card play in PLAY_PHASE."""
    if not player.play_card(selected_id):
        await context.bot.send_message(chat_id=chat_id, text='Not your turn or invalid card!')
        return False
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f'{player.name} played {translate_card(selected_id)}'
    )
    return True


async def chosen_inline_result_handler(update, context):
    """Handle when a player selects an option from the inline query dropdown.

    This processes the bid/partner/card selection and updates the game state.

    Uses session-based routing to find the game: first checks the user's active
    chat session, then falls back to scanning for active player if needed.
    """
    result = update.chosen_inline_result
    user_id = result.from_user.id
    selected_id = result.result_id

    # Primary: Try session-based lookup (user's most recent active chat)
    chat_id = get_user_active_game(redis_client, user_id)
    game = None

    if chat_id:
        game = load_game_from_redis(redis_client, chat_id)

    # Fallback: Scan for any game where this user is playing
    if not game:
        chat_id, game = find_game_by_active_player(redis_client, user_id)

    if not game:
        logger.warning("User %s selected inline result but no active game found", user_id)
        return

    # Find the player object
    player = next((p for p in game.players if p.id == user_id), None)
    if not player:
        logger.warning("User %s not found in game players for chat %s", user_id, chat_id)
        return

    try:
        success = False

        if game.phase == Game.BID_PHASE:
            success = await _handle_bid_selection(player, selected_id, chat_id, context)
            if success:
                # Update session to confirm this chat is the user's active game
                set_user_active_game(redis_client, user_id, chat_id)
                save_game_to_redis(redis_client, chat_id, game)
                await request_bid_in_chat(context.bot, game, chat_id)

        elif game.phase == Game.CALL_PHASE:
            success = await _handle_partner_selection(player, selected_id, chat_id, context)
            if success:
                # Update session to confirm this chat is the user's active game
                set_user_active_game(redis_client, user_id, chat_id)
                save_game_to_redis(redis_client, chat_id, game)

        elif game.phase == Game.PLAY_PHASE:
            success = await _handle_card_play(player, selected_id, chat_id, context)
            if success:
                # Update session to confirm this chat is the user's active game
                set_user_active_game(redis_client, user_id, chat_id)
                save_game_to_redis(redis_client, chat_id, game)

    except Exception:
        logger.exception("Failed to process inline result for user %s in chat %s", user_id, chat_id)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text='An error occurred processing your selection. Please try again.'
            )
        except Exception:
            logger.exception("Failed to send error message to chat %s", chat_id)


# Export handlers for wiring in bot.py
INLINE_HANDLERS = [
    InlineQueryHandler(inline_query_handler),
    ChosenInlineResultHandler(chosen_inline_result_handler)
]

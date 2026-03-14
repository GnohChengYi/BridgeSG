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
from game_utils import (
    translate_bid, translate_card, 
    thumb_url_bid, thumb_url_card, 
    request_bid_in_chat
)

logger = logging.getLogger(__name__)

# --- DRY Helpers ---

def _build_inline_result(id_val, title, content_text, thumbnail_url):
    """Factory to create standardized inline query results."""
    return InlineQueryResultArticle(
        id=str(id_val),
        title=title,
        input_message_content=InputTextMessageContent(content_text),
        thumbnail_url=thumbnail_url
    )

def _get_game_for_user(user_id):
    """Centralized lookup: Session -> Fallback -> None."""
    chat_id = get_user_active_game(redis_client, user_id)
    game = load_game_from_redis(redis_client, chat_id) if chat_id else None
    
    if not game:
        chat_id, game = find_game_by_active_player(redis_client, user_id)
        
    return chat_id, game

# --- Builder Functions ---

def _build_bid_results(game):
    return [_build_inline_result(b, translate_bid(b), translate_bid(b), thumb_url_bid(b)) for b in game.valid_bids()]

def _build_partner_results(player):
    return [_build_inline_result(c, translate_card(c), translate_card(c), thumb_url_card(c)) for c in Game.deck if c not in player.hand]

def _build_card_results(player):
    return [_build_inline_result(c, translate_card(c), translate_card(c), thumb_url_card(c)) for c in player.valid_cards()]

# --- Handlers ---

async def inline_query_handler(update, context):
    query = update.inline_query
    user_id = query.from_user.id
    chat_id, game = _get_game_for_user(user_id)

    if not game or not game.activePlayer or game.activePlayer.id != user_id:
        await query.answer([], cache_time=2, is_personal=True)
        return

    try:
        results = []
        if game.phase == Game.BID_PHASE:
            valid_bids = game.valid_bids()
            logger.info("[inline_query] user_id=%s: BID_PHASE with valid_bids=%s", user_id, valid_bids)
            results = _build_bid_results(game)
        elif game.phase == Game.CALL_PHASE:
            logger.info("[inline_query] user_id=%s: CALL_PHASE", user_id)
            results = _build_partner_results(game.activePlayer)
        elif game.phase == Game.PLAY_PHASE:
            logger.info("[inline_query] user_id=%s: PLAY_PHASE", user_id)
            results = _build_card_results(game.activePlayer)

        logger.info("[inline_query] user_id=%s: Returning %d results (phase=%s)", user_id, len(results), game.phase)
        await query.answer(results, cache_time=2, is_personal=True)
    except Exception:
        logger.exception("Failed to build inline query results for user %s", user_id)
        await query.answer([], cache_time=2, is_personal=True)


async def chosen_inline_result_handler(update, context):
    result = update.chosen_inline_result
    user_id = result.from_user.id
    selected_id = result.result_id
    chat_id, game = _get_game_for_user(user_id)

    if not game:
        logger.warning("User %s selected inline result but no active game found", user_id)
        return

    player = next((p for p in game.players if p.id == user_id), None)
    if not player:
        return

    try:
        success = False
        if game.phase == Game.BID_PHASE:
            success = await _handle_bid_selection(player, selected_id, chat_id, context)
            if success: await request_bid_in_chat(context.bot, game, chat_id)
        elif game.phase == Game.CALL_PHASE:
            success = await _handle_partner_selection(player, selected_id, chat_id, context)
        elif game.phase == Game.PLAY_PHASE:
            success = await _handle_card_play(player, selected_id, chat_id, context)

        if success:
            set_user_active_game(redis_client, user_id, chat_id)
            save_game_to_redis(redis_client, chat_id, game)

    except Exception:
        logger.exception("Failed to process inline result for user %s", user_id)


# --- Selection Handlers ---

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


INLINE_HANDLERS = [
    InlineQueryHandler(inline_query_handler),
    ChosenInlineResultHandler(chosen_inline_result_handler)
]
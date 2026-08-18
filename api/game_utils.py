import logging
from typing import List
from telegram.constants import ParseMode
import asyncio

from bridge import Game
from store import redis_client, save_game_to_redis

logger = logging.getLogger(__name__)


def format_hand(hand: List[str]) -> str:
    """Return a readable string for a hand (list of card codes like 'SA').

    Group by suit and replace suit letters with symbols. Keeps logic small and
    deterministic so tests are easy to write.
    """
    if not hand:
        return "(no cards)"
    suits = {"C": [], "D": [], "H": [], "S": []}
    for card in hand:
        if not card or len(card) < 2:
            continue
        suits[card[0]].append(card[1])
    parts = []
    mapping = {"C": "♣️", "D": "♦️", "H": "❤️", "S": "♠️"}
    try:
        order = Game.numbers
        for k in ("C", "D", "H", "S"):
            cards = suits[k]
            cards_sorted = sorted(cards, key=lambda x: order.index(x)) if cards else []
            if cards_sorted:
                parts.append(f"{mapping[k]}: {' '.join(cards_sorted)}")
    except Exception:
        for k in ("C", "D", "H", "S"):
            if suits[k]:
                parts.append(f"{mapping[k]}: {' '.join(suits[k])}")
    return "\n".join(parts)


async def notify_players_hands(bot, game, chat_id: int):
    """DM each human player their hand after game start.

    This is intentionally tolerant: failures are logged but don't stop the loop.
    """
    for player in game.players:
        try:
            if getattr(player, "isAI", False):
                continue
            user_chat_id = player.id
            hand_text = format_hand(getattr(player, "hand", []))
            dm_text = f"Your hand for the game:\n{hand_text}"
            await bot.send_message(chat_id=user_chat_id, text=dm_text)
        except Exception:
            logger.exception("Failed to DM hand to player %s for chat %s", getattr(player, "id", None), chat_id)


def translate_bid(bid: str) -> str:
    """Make bids more readable for chat prompts."""
    if not bid:
        return ""
    if bid == Game.PASS:
        return Game.PASS
    b = bid
    b = b.replace(Game.CLUBS, '♣️')
    b = b.replace(Game.DIAMONDS, '♦️')
    b = b.replace(Game.HEARTS, '❤️')
    b = b.replace(Game.SPADES, '♠️')
    b = b.replace(Game.NO_TRUMP, '🚫')
    return b


def parse_display_card(display: str) -> str:
    """Convert a visible card like '6♦️' or 'A♠️' into the canonical bridge code.

    The in-game format is suit-first (e.g. 'D6', 'SA'), while Telegram often
    sends the display as rank-first with emoji suit markers (e.g. '6♦️').
    """
    if not display:
        return ''
    s = display.strip().upper().replace('\uFE0F', '')
    if not s:
        return ''
    if s == Game.PASS:
        return Game.PASS

    # Normalize visible suit symbols back to canonical letters.
    mapping = {
        '♣': Game.CLUBS,
        '♦': Game.DIAMONDS,
        '♥': Game.HEARTS,
        '❤': Game.HEARTS,
        '♠': Game.SPADES,
        'C': Game.CLUBS,
        'D': Game.DIAMONDS,
        'H': Game.HEARTS,
        'S': Game.SPADES,
    }
    for symbol, suit in mapping.items():
        s = s.replace(symbol, suit)

    # Already in canonical suit-first form: 'D6' or 'SA'.
    if len(s) >= 2 and s[0] in Game.suits and s[1] in Game.numbers + '10':
        rank = s[1:]
        if rank == '10':
            rank = 'T'
        return f"{s[0]}{rank}"

    # Rank-first form like '6D' or 'AS' from a Telegram plain-text fallback.
    if len(s) >= 2 and s[-1] in Game.suits:
        rank = s[:-1]
        if rank == '10':
            rank = 'T'
        return f"{s[-1]}{rank}"

    return s


def parse_display_bid(display: str) -> str:
    """Convert a user-visible bid (e.g. '1♣️' or 'PASS' or '1🚫') to the
    canonical internal bid id used by `Game` (e.g. '1C', 'PASS', '1N').

    This helps handle Telegram clients that deliver inline choices as
    plain `message.text` using emoji/symbols for suits.
    """
    if not display:
        return ''
    s = display.strip().upper()
    if s == Game.PASS:
        return Game.PASS

    normalized = s.replace('♣️', Game.CLUBS)
    normalized = normalized.replace('♣', Game.CLUBS)
    normalized = normalized.replace('♦️', Game.DIAMONDS)
    normalized = normalized.replace('♦', Game.DIAMONDS)
    normalized = normalized.replace('❤️', Game.HEARTS)
    normalized = normalized.replace('❤', Game.HEARTS)
    normalized = normalized.replace('♥️', Game.HEARTS)
    normalized = normalized.replace('♥', Game.HEARTS)
    normalized = normalized.replace('♠️', Game.SPADES)
    normalized = normalized.replace('♠', Game.SPADES)
    normalized = normalized.replace('\uFE0F', '')

    # Card text is not a bid; convert it using the card parser before we decide
    # whether the text is a bid or a card. This prevents Telegram rank-first
    # card messages such as '6♦️' from being interpreted as the invalid '6D'.
    if len(normalized) >= 2 and (
        (normalized[0] in Game.numbers and normalized[-1] in Game.suits) or
        (normalized[0] in Game.suits and normalized[1] in Game.numbers + '10')
    ):
        return parse_display_card(s)

    # map visible suit symbols back to canonical letters
    s = normalized
    s = s.replace('🚫', Game.NO_TRUMP)
    s = s.replace('N', Game.NO_TRUMP) if len(s) == 2 and s[1] == 'N' else s
    return s


async def request_bid_in_chat(bot, game, chat_id: int):
    """Post a prompt in the chat asking the active player to bid.

    This is a minimal implementation adapted from the original flow: it
    composes a short message and mentions the active player using tg://user.
    """
    try:
        # If the game has already moved out of bidding, nothing to prompt.
        if game.phase != Game.BID_PHASE:
            if game.phase == Game.CALL_PHASE:
                player = game.activePlayer
                if getattr(player, 'isAI', False):
                    try:
                        card = player.call_partner()
                        try:
                            save_game_to_redis(redis_client, chat_id, game)
                            await bot.send_message(chat_id=chat_id, text=f"{player.name} called partner: {translate_card(card)}")
                        except Exception:
                            logger.exception("Failed to announce AI partner call for player %s in chat %s", getattr(player, 'id', None), chat_id)
                        # After AI calls partner, phase changes to PLAY_PHASE.
                        # Persist the updated state before we resume the turn flow,
                        # then continue with the next player regardless of whether
                        # that player is AI or human.
                        if game.phase == Game.PLAY_PHASE:
                            save_game_to_redis(redis_client, chat_id, game)
                            if getattr(game.activePlayer, 'isAI', False):
                                await request_card_play_in_chat(bot, game, chat_id)
                            else:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text=f"[{game.activePlayer.name}](tg://user?id={game.activePlayer.id}), your turn to play!",
                                    parse_mode=ParseMode.MARKDOWN,
                                )
                    except Exception:
                        logger.exception("AI call_partner failed for player %s in chat %s", getattr(player, 'id', None), chat_id)
                    return
                await bot.send_message(chat_id=chat_id, text=f"[{player.name}](tg://user?id={player.id}), you won the bid! Choose your partner's card!", parse_mode=ParseMode.MARKDOWN)
            return

        # Loop so that consecutive AI turns are played out immediately.
        while game.phase == Game.BID_PHASE and getattr(game.activePlayer, 'isAI', False):
            player = game.activePlayer
            if not player:
                return

            try:
                bid = player.make_bid()
            except Exception:
                logger.exception("AI make_bid failed for player %s in chat %s", getattr(player, 'id', None), chat_id)
                return

            try:
                await bot.send_message(chat_id=chat_id, text=f"{player.name}: {translate_bid(bid)}")
            except Exception:
                logger.exception("Failed to announce AI bid for player %s in chat %s", getattr(player, 'id', None), chat_id)

            try:
                await asyncio.sleep(1)
            except Exception:
                pass

            if game.phase != Game.BID_PHASE:
                break

        if game.phase != Game.BID_PHASE:
            await request_bid_in_chat(bot, game, chat_id)
            return

        # Active player is human — prompt them and return
        player = game.activePlayer
        if not player:
            return

        current_bid = translate_bid(getattr(game, 'bid', Game.PASS))
        text = f"Current Bid: {current_bid}\n"
        text += f"[{player.name}](tg://user?id={player.id}), your turn to bid!"
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        return
    except Exception:
        logger.exception("Failed to post bid prompt for chat %s", chat_id)


def translate_card(card: str) -> str:
    """Small helper to make a card code readable, e.g. 'SA' -> 'A♠️'."""
    if not card:
        return ''
    c = card[::-1]
    c = c.replace('T', '10')
    c = c.replace(Game.CLUBS, '♣️')
    c = c.replace(Game.DIAMONDS, '♦️')
    c = c.replace(Game.HEARTS, '❤️')
    c = c.replace(Game.SPADES, '♠️')
    return c


def _get_suit_thumb_url(suit: str) -> str:
    """Helper to get thumbnail URL for a suit symbol."""
    suit_urls = {
        Game.CLUBS: 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Card_suit_club.svg/240px-Card_suit_club.svg.png',
        Game.DIAMONDS: 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Card_suit_diamond.svg/240px-Card_suit_diamond.svg.png',
        Game.HEARTS: 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f4/Card_suit_heart.svg/240px-Card_suit_heart.svg.png',
        Game.SPADES: 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Card_suit_spade.svg/240px-Card_suit_spade.svg.png',
    }
    return suit_urls.get(suit, '')


def thumb_url_bid(bid: str) -> str:
    """Return thumbnail URL for a bid based on suit/type.
    
    Used for inline query results to show visual icons.
    """
    if bid == Game.PASS:
        return 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/VisualEditor_-_Icon_-_Close.svg/240px-VisualEditor_-_Icon_-_Close.svg.png'
    if bid[1] == Game.NO_TRUMP:
        return 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_sign.svg/240px-No_sign.svg.png'
    return _get_suit_thumb_url(bid[1])


def thumb_url_card(card: str) -> str:
    """Return thumbnail URL for a card based on suit.
    
    Used for inline query results to show visual icons.
    """
    if not card:
        return ''
    return _get_suit_thumb_url(card[0])


async def request_card_play_in_chat(bot, game, chat_id: int):
    """Post card play prompts in the chat during PLAY_PHASE.
    
    Handles consecutive AI card plays in a loop, completing tricks as they
    occur. When an AI player is done or the game ends, transitions to prompting
    the next human player or announcing game results.
    """
    try:
        # Loop: execute AI card plays immediately until game ends or human's turn
        while game.phase == Game.PLAY_PHASE and getattr(game.activePlayer, 'isAI', False):
            player = game.activePlayer
            if not player:
                return

            try:
                card = player.play_card()
                if not card:
                    logger.warning("AI play_card failed for player %s in chat %s", player.id, chat_id)
                    return
                save_game_to_redis(redis_client, chat_id, game)
            except Exception:
                logger.exception("AI play_card failed for player %s in chat %s", getattr(player, 'id', None), chat_id)
                return

            try:
                await bot.send_message(chat_id=chat_id, text=f"{player.name} played {translate_card(card)}")
            except Exception:
                logger.exception("Failed to announce AI card play for player %s in chat %s", getattr(player, 'id', None), chat_id)

            try:
                await asyncio.sleep(1)
            except Exception:
                pass

            # Check if all 4 cards have been played in the current trick
            if all(game.currentTrick):  # All 4 positions filled
                try:
                    game.complete_trick()
                    try:
                        winner = game.players[0]  # After reordering, winner is first
                        await bot.send_message(chat_id=chat_id, text=f"{winner.name} won the trick!")
                    except Exception:
                        logger.exception("Failed to announce trick winner in chat %s", chat_id)
                except Exception:
                    logger.exception("Failed to complete trick in chat %s", chat_id)
                    return

            # Break if game has ended
            if game.phase == Game.END_PHASE:
                break

        # Handle game end
        if game.phase == Game.END_PHASE:
            try:
                winners_str = ', '.join(p.name for p in game.winners)
                await bot.send_message(chat_id=chat_id, text=f"Game ended! Winners: {winners_str}")
            except Exception:
                logger.exception("Failed to announce game end in chat %s", chat_id)
            return

        save_game_to_redis(redis_client, chat_id, game)

        # If game is still in PLAY_PHASE and activePlayer is human, prompt them
        if game.phase == Game.PLAY_PHASE:
            player = game.activePlayer
            if player and not getattr(player, 'isAI', False):
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"[{player.name}](tg://user?id={player.id}), your turn to play!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    logger.exception("Failed to prompt human player in chat %s", chat_id)
    except Exception:
        logger.exception("Failed in card play phase for chat %s", chat_id)


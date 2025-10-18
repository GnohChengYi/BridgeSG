import logging
from typing import List
from telegram.constants import ParseMode
import asyncio

from bridge import Game

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


def _translate_bid(bid: str) -> str:
    """Small helper to make bids more readable for chat prompts."""
    if not bid:
        return ""
    if bid == Game.PASS:
        return Game.PASS
    b = bid
    b = b.replace('C', '♣️')
    b = b.replace('D', '♦️')
    b = b.replace('H', '❤️')
    b = b.replace('S', '♠️')
    b = b.replace('N', '🚫')
    return b


async def request_bid_in_chat(bot, game, chat_id: int):
    """Post a prompt in the chat asking the active player to bid.

    This is a minimal implementation adapted from the original flow: it
    composes a short message and mentions the active player using tg://user.
    """
    try:
        # Loop so that consecutive AI turns are played out immediately.
        while True:
            player = game.activePlayer
            if not player:
                return

            # If we've moved to CALL_PHASE, stop here and let caller decide next step
            if game.phase == Game.CALL_PHASE:
                break

            # If the active player is an AI, have it bid automatically and announce
            if getattr(player, "isAI", False):
                try:
                    bid = player.make_bid()
                except Exception:
                    logger.exception("AI make_bid failed for player %s in chat %s", getattr(player, 'id', None), chat_id)
                    return

                try:
                    await bot.send_message(chat_id=chat_id, text=f"{player.name}: {_translate_bid(bid)}")
                except Exception:
                    logger.exception("Failed to announce AI bid for player %s in chat %s", getattr(player, 'id', None), chat_id)

                # small pause to avoid rapid-fire messages
                try:
                    await asyncio.sleep(1)
                except Exception:
                    # sleep is best-effort
                    pass

                # continue the loop; if next player is human, the loop will break below
                # also if bidding ended or moved to CALL_PHASE, the loop will exit
                if game.phase != Game.BID_PHASE:
                    break
                continue

            # Active player is human — prompt them and return
            current_bid = _translate_bid(getattr(game, 'bid', Game.PASS))
            text = f"Current Bid: {current_bid}\n"
            text += f"[{player.name}](tg://user?id={player.id}), your turn to bid!"
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
            return

        # If we exit loop and are in CALL_PHASE, handle partner selection.
        if game.phase == Game.CALL_PHASE:
            player = game.activePlayer
            if getattr(player, 'isAI', False):
                try:
                    card = player.call_partner()
                    # announce the AI's partner call (translate card)
                    try:
                        await bot.send_message(chat_id=chat_id, text=f"{player.name} called partner: {translate_card(card)}")
                    except Exception:
                        logger.exception("Failed to announce AI partner call for player %s in chat %s", getattr(player, 'id', None), chat_id)
                except Exception:
                    logger.exception("AI call_partner failed for player %s in chat %s", getattr(player, 'id', None), chat_id)
                return
            else:
                # human needs to choose partner
                await bot.send_message(chat_id=chat_id, text=f"[{player.name}](tg://user?id={player.id}), you won the bid! Choose your partner's card!", parse_mode=ParseMode.MARKDOWN)
                return
    except Exception:
        logger.exception("Failed to post bid prompt for chat %s", chat_id)


def translate_card(card: str) -> str:
    """Small helper to make a card code readable, e.g. 'SA' -> 'A♠️'."""
    if not card:
        return ''
    c = card[::-1]
    c = c.replace('T', '10')
    c = c.replace('C', '♣️')
    c = c.replace('D', '♦️')
    c = c.replace('H', '❤️')
    c = c.replace('S', '♠️')
    return c

import logging
from typing import List

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
            dm_text = f"Your hand for the game in chat {chat_id}:\n{hand_text}"
            await bot.send_message(chat_id=user_chat_id, text=dm_text)
        except Exception:
            logger.exception("Failed to DM hand to player %s for chat %s", getattr(player, "id", None), chat_id)

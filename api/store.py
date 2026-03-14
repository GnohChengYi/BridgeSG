import os
import json
import logging
from datetime import datetime
from typing import Optional

import redis

from bridge import Game

logger = logging.getLogger(__name__)


def create_redis_client(url: str):
    """Create a StrictRedis client and verify connectivity.

    Raises SystemExit(1) if the URL is not provided or connectivity fails.
    """
    if not url:
        logger.error("REDIS_URL not set; Redis is required.")
        raise SystemExit(1)
    try:
        client = redis.StrictRedis.from_url(url)
        client.ping()
        return client
    except Exception:
        logger.exception("Failed to create/connect to Redis at URL: %s", url)
        raise SystemExit(1)


def save_join_message(redis_client, chat_id: int, message_id: int) -> bool:
    """Save the bot's join-message id for a chat so callbacks can reference it."""
    try:
        redis_client.set(f"join_message:{chat_id}", str(message_id))
        return True
    except Exception:
        logger.exception("Failed to save join message id for chat %s", chat_id)
        return False


def load_join_message(redis_client, chat_id: int) -> Optional[int]:
    try:
        v = redis_client.get(f"join_message:{chat_id}")
        if not v:
            return None
        return int(v)
    except Exception:
        logger.exception("Failed to load join message id for chat %s", chat_id)
        return None


def delete_join_message(redis_client, chat_id: int) -> bool:
    try:
        redis_client.delete(f"join_message:{chat_id}")
        return True
    except Exception:
        logger.exception("Failed to delete join message id for chat %s", chat_id)
        return False


def save_game_to_redis(redis_client, chat_id: int, game: Game) -> bool:
    try:
        redis_client.set(f"game:{chat_id}", json.dumps(game.to_dict()))
        return True
    except Exception:
        logger.exception("Failed to save game to Redis for chat %s", chat_id)
        return False


def game_exists_in_redis(redis_client, chat_id: int) -> bool:
    try:
        return redis_client.exists(f"game:{chat_id}") == 1
    except Exception:
        logger.exception("Error checking game existence in Redis for chat %s", chat_id)
        return False


def load_game_from_redis(redis_client, chat_id: int):
    try:
        data = redis_client.get(f"game:{chat_id}")
        if not data:
            return None
        return Game.from_dict(json.loads(data))
    except Exception:
        logger.exception("Failed to load game from Redis for chat %s", chat_id)
        return None


def set_user_active_game(redis_client, user_id: int, chat_id: int) -> bool:
    """Store the active chat context for a user in Redis.

    This enables session-based routing for inline queries, which don't include
    chat context. Whenever a user interacts with a chat (command, callback, etc),
    we record which chat they're actively using so inline queries can retrieve it.

    Key format: user:{user_id}:active_chat
    """
    try:
        redis_client.set(f"user:{user_id}:active_chat", str(chat_id))
        return True
    except Exception:
        logger.exception("Failed to set active game for user %s in chat %s", user_id, chat_id)
        return False


def get_user_active_game(redis_client, user_id: int) -> Optional[int]:
    """Retrieve the active chat context for a user from Redis.

    Returns the chat_id if found, else None.
    This is the primary mechanism for inline queries to determine which game
    the user is interacting with, since inline_query payloads contain no chat context.

    Key format: user:{user_id}:active_chat
    """
    try:
        chat_id = redis_client.get(f"user:{user_id}:active_chat")
        if not chat_id:
            return None
        return int(chat_id)
    except Exception:
        logger.exception("Failed to get active game for user %s", user_id)
        return None


def find_game_by_active_player(redis_client, user_id: int):
    """Scan Redis for a game where the given user is the active player.

    Returns (chat_id, game) tuple if found, else (None, None).
    This is a fallback mechanism used when user session lookup fails.
    For inline query handlers, prefer get_user_active_game + load_game_from_redis first.
    """
    try:
        # Scan all game:* keys in Redis
        for key in redis_client.scan_iter(match="game:*"):
            try:
                data = redis_client.get(key)
                if not data:
                    continue
                game_dict = json.loads(data)
                active_player_id = game_dict.get('activePlayer')
                if active_player_id == user_id:
                    # Extract chat_id from key (format is "game:123456")
                    chat_id = int(key.decode('utf-8').split(':')[1])
                    game = Game.from_dict(game_dict)
                    return (chat_id, game)
            except Exception:
                logger.exception("Failed to parse game from key %s", key)
                continue
        return (None, None)
    except Exception:
        logger.exception("Failed to scan Redis for user %s", user_id)
        return (None, None)


# Create a module-level redis client at import time so callers can import
# `store.redis_client` and use it. It fails fast if REDIS_URL is missing.
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = create_redis_client(REDIS_URL)

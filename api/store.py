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


# TODO update to show proper start message
def handle_start_for_chat(redis_client) -> Optional[str]:
    """Synchronous helper that updates Redis and returns reply text.

    Designed to be called from sync contexts as well as async handlers.
    """
    try:
        current_time = datetime.now().isoformat()
        redis_client.set("last_start_time", current_time)
        retrieved = redis_client.get("last_start_time")
        retrieved_time = retrieved.decode("utf-8") if retrieved else current_time
        return f"The last start time was: {retrieved_time}"
    except Exception:
        logger.exception("Error in handle_start_for_chat")
        return None


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


# Create a module-level redis client at import time so callers can import
# `store.redis_client` and use it. It fails fast if REDIS_URL is missing.
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = create_redis_client(REDIS_URL)

"""Redis-backed store for /btw context injection messages.

Messages are pushed to a per-thread Redis list and atomically consumed
by the BtwMiddleware before each LLM call. TTL prevents unbounded
growth if a thread is abandoned.
"""

from __future__ import annotations

import json
import time
from typing import Any

from deep_agent.aegra.redis import REDIS_KEY_PREFIX, get_redis_client
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

BTW_KEY_PREFIX = f"{REDIS_KEY_PREFIX}btw:"
DEFAULT_TTL_SECONDS = 3600
MAX_MESSAGE_LENGTH = 2000
MAX_QUEUE_DEPTH = 50


def _btw_key(thread_id: str) -> str:
    """Build the Redis key for a thread's /btw message queue."""
    return f"{BTW_KEY_PREFIX}{thread_id}"


def push_btw_message(
    thread_id: str,
    message: str,
    *,
    user_id: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> int:
    """Push a /btw message onto the thread's Redis queue.

    Args:
        thread_id: LangGraph thread identifier.
        message: User-provided context message (max MAX_MESSAGE_LENGTH chars).
        user_id: Optional user identifier for audit logging.
        ttl_seconds: TTL for the entire queue key.

    Returns:
        Current queue depth after push.

    Raises:
        RuntimeError: If Redis is unavailable.
        ValueError: If message exceeds MAX_MESSAGE_LENGTH or is empty.
    """
    if not message or not message.strip():
        raise ValueError("Message cannot be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"Message exceeds {MAX_MESSAGE_LENGTH} characters "
            f"(got {len(message)})"
        )

    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis unavailable — /btw messages require Redis")

    key = _btw_key(thread_id)
    envelope = json.dumps({
        "message": message.strip(),
        "user_id": user_id or "anonymous",
        "timestamp": time.time(),
    })

    pipe = client.pipeline()
    pipe.rpush(key, envelope)
    pipe.ltrim(key, -MAX_QUEUE_DEPTH, -1)
    pipe.expire(key, ttl_seconds)
    results = pipe.execute()

    depth = results[0]
    logger.info(
        "btw_message_pushed",
        thread_id=thread_id,
        user_id=user_id or "anonymous",
        queue_depth=depth,
        message_length=len(message),
    )
    return depth


def consume_btw_messages(thread_id: str) -> list[dict[str, Any]]:
    """Atomically consume all pending /btw messages for a thread.

    Uses a Redis pipeline to LRANGE + DELETE in one round-trip,
    ensuring each message is consumed exactly once.

    Args:
        thread_id: LangGraph thread identifier.

    Returns:
        List of message envelopes (dicts with 'message', 'user_id',
        'timestamp' keys). Empty list if no messages or Redis unavailable.
    """
    client = get_redis_client()
    if client is None:
        return []

    key = _btw_key(thread_id)

    pipe = client.pipeline()
    pipe.lrange(key, 0, -1)
    pipe.delete(key)
    results = pipe.execute()

    raw_messages = results[0]
    if not raw_messages:
        return []

    messages: list[dict[str, Any]] = []
    for raw in raw_messages:
        try:
            messages.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            logger.warning("btw_message_corrupt", thread_id=thread_id, raw=raw)

    if messages:
        logger.info(
            "btw_messages_consumed",
            thread_id=thread_id,
            count=len(messages),
        )

    return messages


def get_queue_depth(thread_id: str) -> int:
    """Return the current number of pending /btw messages.

    Args:
        thread_id: LangGraph thread identifier.

    Returns:
        Queue depth, or 0 if Redis unavailable.
    """
    client = get_redis_client()
    if client is None:
        return 0
    return client.llen(_btw_key(thread_id))

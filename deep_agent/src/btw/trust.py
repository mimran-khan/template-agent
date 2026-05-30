"""Session-level trust management for HITL tool approval.

When a user clicks "Approve All for Session", a Redis flag is set that
causes HumanInTheLoopMiddleware to skip interrupt() for the remainder
of the thread.  The flag expires automatically and can be revoked.
"""

from __future__ import annotations

from deep_agent.aegra.redis import REDIS_KEY_PREFIX, get_redis_client
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

TRUST_KEY_PREFIX = f"{REDIS_KEY_PREFIX}trust:"
DEFAULT_TRUST_TTL = 7200  # 2 hours


def _trust_key(thread_id: str) -> str:
    """Build the Redis key for a thread's trust level."""
    return f"{TRUST_KEY_PREFIX}{thread_id}"


def get_trust_level(thread_id: str) -> str | None:
    """Return the current trust level for a thread.

    Args:
        thread_id: LangGraph thread identifier.

    Returns:
        Trust level string (e.g. ``"approve_all"``) or ``None``
        if no trust is set or Redis is unavailable.
    """
    client = get_redis_client()
    if client is None:
        return None
    val = client.get(_trust_key(thread_id))
    if val is None:
        return None
    return val if isinstance(val, str) else val.decode("utf-8")


def set_trust_level(
    thread_id: str,
    level: str,
    ttl: int = DEFAULT_TRUST_TTL,
) -> None:
    """Set the trust level for a thread.

    Args:
        thread_id: LangGraph thread identifier.
        level: Trust level string (e.g. ``"approve_all"``).
        ttl: Time-to-live in seconds.

    Raises:
        RuntimeError: If Redis is unavailable.
    """
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis unavailable — trust requires Redis")
    client.set(_trust_key(thread_id), level, ex=ttl)
    logger.info(
        "trust_level_set",
        thread_id=thread_id,
        level=level,
        ttl=ttl,
    )


def revoke_trust(thread_id: str) -> None:
    """Revoke trust for a thread (delete the Redis key).

    Args:
        thread_id: LangGraph thread identifier.

    Raises:
        RuntimeError: If Redis is unavailable.
    """
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis unavailable — trust requires Redis")
    client.delete(_trust_key(thread_id))
    logger.info("trust_revoked", thread_id=thread_id)


def is_trusted(thread_id: str) -> bool:
    """Check whether the thread has approve-all trust.

    Convenience wrapper over :func:`get_trust_level`.

    Args:
        thread_id: LangGraph thread identifier.

    Returns:
        ``True`` if the trust level is ``"approve_all"``.
    """
    return get_trust_level(thread_id) == "approve_all"

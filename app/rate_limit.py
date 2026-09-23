"""In-memory sliding-window rate limiter for the co-pilot/analyst chat
endpoints — guards against a runaway frontend loop, a buyer mashing send,
or accidental scripted spam burning through paid LLM credits, independent
of the daily budget cap in app/llm.py (that catches total spend; this
catches a burst before it even reaches the model).

In-memory only: correct for this app's single-process deployment. Would
need a shared store (Redis, DB row with a lock, etc.) behind multiple
worker processes.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from app.config import settings

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


class RateLimitExceededError(RuntimeError):
    """Raised before an LLM call is attempted once the caller has sent too
    many messages for `key` within the configured window."""


def check_rate_limit(key: str) -> None:
    now = time.time()
    window = settings.llm_chat_rate_limit_window_s
    limit = settings.llm_chat_rate_limit_count
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            minutes = max(1, window // 60)
            raise RateLimitExceededError(
                f"Too many messages — limit is {limit} per {minutes} minute(s). Please wait a bit and try again."
            )
        q.append(now)

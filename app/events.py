"""Minimal in-process SSE broadcaster (PRD §9 event types). One process,
one demo session — good enough for this app; a multi-worker deployment
would need a real pub/sub backend instead.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

_subscribers: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def emit(event_type: str, data: dict[str, Any]) -> None:
    payload = f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
    for q in list(_subscribers):
        q.put_nowait(payload)

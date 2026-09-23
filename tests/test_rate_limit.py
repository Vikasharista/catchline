"""Sliding-window rate limiter guarding the chat endpoints against a
runaway loop or spam burning through paid LLM credits, independent of the
daily budget cap (this catches a burst before it even reaches the model).
"""
import pytest

import app.rate_limit as rate_limit_module
from app.rate_limit import RateLimitExceededError, check_rate_limit


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    from collections import defaultdict, deque

    monkeypatch.setattr(rate_limit_module, "_hits", defaultdict(deque))
    monkeypatch.setattr(rate_limit_module.settings, "llm_chat_rate_limit_count", 3)
    monkeypatch.setattr(rate_limit_module.settings, "llm_chat_rate_limit_window_s", 60)


def test_allows_up_to_the_limit():
    for _ in range(3):
        check_rate_limit("rfx:1")  # should not raise


def test_raises_once_limit_is_exceeded():
    for _ in range(3):
        check_rate_limit("rfx:1")
    with pytest.raises(RateLimitExceededError):
        check_rate_limit("rfx:1")


def test_different_keys_are_independent():
    for _ in range(3):
        check_rate_limit("rfx:1")
    check_rate_limit("rfx:2")  # different RFQ, should not raise


def test_resets_after_the_window_passes(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: t[0])

    for _ in range(3):
        check_rate_limit("rfx:1")
    with pytest.raises(RateLimitExceededError):
        check_rate_limit("rfx:1")

    t[0] += 61  # past the 60s window
    check_rate_limit("rfx:1")  # should not raise now

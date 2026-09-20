"""Client errors (bad request, auth, billing) shouldn't burn the retry
budget — only transient errors should. Caught live: an exhausted Anthropic
credit balance was retried 3 times (~6s wasted) before falling back to
Gemini, even though retrying an identical request never fixes a billing
error.
"""
import litellm

from app.llm import _is_retryable


def test_bad_request_error_is_not_retryable():
    exc = litellm.BadRequestError(message="credit balance too low", model="x", llm_provider="anthropic")
    assert _is_retryable(exc) is False


def test_authentication_error_is_not_retryable():
    exc = litellm.AuthenticationError(message="invalid key", model="x", llm_provider="anthropic")
    assert _is_retryable(exc) is False


def test_rate_limit_error_is_retryable():
    exc = litellm.RateLimitError(message="rate limited", model="x", llm_provider="anthropic")
    assert _is_retryable(exc) is True


def test_service_unavailable_is_retryable():
    exc = litellm.ServiceUnavailableError(message="high demand", model="x", llm_provider="gemini")
    assert _is_retryable(exc) is True


def test_unrecognized_exception_defaults_to_retryable():
    assert _is_retryable(ConnectionError("network blip")) is True

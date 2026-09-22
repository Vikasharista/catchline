"""LLM_FALLBACK now accepts a comma-separated list, not just one model —
added after a live outage where Gemini (the sole fallback) returned
sustained 503s while Anthropic was already out of credit, taking the
co-pilot down entirely. Verifies complete() walks the whole chain in
order rather than giving up after the first fallback.
"""
import litellm
import pytest

import app.llm as llm_module
from app.llm import complete


@pytest.fixture
def three_model_chain(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_model", "anthropic/claude-x")
    monkeypatch.setattr(llm_module.settings, "llm_fallback", "gemini/flash-lite,groq/llama-3.3-70b-versatile")


def test_falls_through_every_model_in_the_comma_separated_list(three_model_chain, monkeypatch):
    attempted_models = []

    def fake_completion(model, **kwargs):
        attempted_models.append(model)
        if model != "groq/llama-3.3-70b-versatile":
            raise litellm.BadRequestError(message="down", model=model, llm_provider="x")

        class FakeChoice:
            class message:
                content = "ok from groq"
                tool_calls = None

        class FakeResponse:
            choices = [FakeChoice()]

        return FakeResponse()

    monkeypatch.setattr(litellm, "completion", fake_completion)

    result = complete([{"role": "user", "content": "hi"}], max_retries=0)

    assert attempted_models == ["anthropic/claude-x", "gemini/flash-lite", "groq/llama-3.3-70b-versatile"]
    assert result.text == "ok from groq"
    assert result.model == "groq/llama-3.3-70b-versatile"


def test_raises_when_every_model_in_the_chain_fails(three_model_chain, monkeypatch):
    def always_fails(model, **kwargs):
        raise litellm.BadRequestError(message="down", model=model, llm_provider="x")

    monkeypatch.setattr(litellm, "completion", always_fails)

    with pytest.raises(RuntimeError, match="All LLM attempts failed"):
        complete([{"role": "user", "content": "hi"}], max_retries=0)

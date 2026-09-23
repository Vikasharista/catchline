"""Regression test: run_tool_loop must reconstruct the assistant message's
tool_calls in the OpenAI/litellm-expected shape ({"type": "function",
"function": {"name", "arguments"}}), not the flat LLMResult.tool_calls
format — otherwise a second loop iteration sends a malformed message and
Anthropic (via litellm) rejects it with a tool_use_id mismatch. Caught by
manual live testing; see app/llm.py history.
"""
import json

from app.config import settings
from app.llm import LLMResult, run_tool_loop


def test_reconstructed_assistant_message_has_openai_tool_call_shape(monkeypatch):
    calls = []

    def fake_complete(messages, *, tools=None, prompt_version="v1", **kwargs):
        calls.append([dict(m) for m in messages])
        if len(calls) == 1:
            return LLMResult(text=None, tool_calls=[{"id": "call_1", "name": "lookup", "arguments": {"x": 1}}])
        return LLMResult(text="done", tool_calls=[])

    monkeypatch.setattr("app.llm.complete", fake_complete)

    text, transcript = run_tool_loop(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "lookup", "parameters": {}}}],
        tool_impls={"lookup": lambda x: {"ok": x}},
    )

    assert text == "done"
    assert len(transcript) == 1

    # the second complete() call must have received a well-formed assistant
    # message with tool_calls in the type/function shape, plus a matching
    # tool result message right after it.
    second_call_messages = calls[1]
    assistant_msg = next(m for m in second_call_messages if m["role"] == "assistant")
    assert assistant_msg["tool_calls"][0]["type"] == "function"
    assert assistant_msg["tool_calls"][0]["id"] == "call_1"
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "lookup"
    assert json.loads(assistant_msg["tool_calls"][0]["function"]["arguments"]) == {"x": 1}

    tool_msg = next(m for m in second_call_messages if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_1"


def test_uses_chat_scoped_max_tokens_by_default(monkeypatch):
    """Chat replies are short; run_tool_loop shouldn't use complete()'s
    8192 default sized for structured-extraction documents."""
    seen_max_tokens = []

    def fake_complete(messages, *, tools=None, prompt_version="v1", max_tokens=None, **kwargs):
        seen_max_tokens.append(max_tokens)
        return LLMResult(text="done", tool_calls=[])

    monkeypatch.setattr("app.llm.complete", fake_complete)

    run_tool_loop([{"role": "user", "content": "hi"}], tools=[], tool_impls={})

    assert seen_max_tokens == [settings.llm_chat_max_tokens]


def test_malformed_tool_call_feeds_back_error_instead_of_crashing(monkeypatch):
    """Regression test: a real 502 was hit live when the model called
    propose_change with some required arguments missing (e.g. no `target`),
    which propagated as a raw TypeError ("propose_change() missing 4
    required positional arguments...") all the way out of run_tool_loop,
    killing the request and showing the buyer a Python-error-shaped
    message. The tool call should instead get a tool-result error it (or
    the model) can act on, and the loop should keep going.
    """
    calls = []

    def fake_complete(messages, *, tools=None, prompt_version="v1", **kwargs):
        calls.append(None)
        if len(calls) == 1:
            return LLMResult(
                text=None, tool_calls=[{"id": "call_1", "name": "propose_change", "arguments": {"section": "lines"}}]
            )
        return LLMResult(text="done", tool_calls=[])

    monkeypatch.setattr("app.llm.complete", fake_complete)

    def propose_change(section, op, target, value, reason, origin):
        raise AssertionError("should never be called with missing arguments")

    text, transcript = run_tool_loop(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "propose_change", "parameters": {}}}],
        tool_impls={"propose_change": propose_change},
    )

    assert text == "done"
    assert len(transcript) == 1
    assert "error" in transcript[0]["result"]
    assert "propose_change" in transcript[0]["result"]["error"]


def test_explicit_max_tokens_overrides_the_default(monkeypatch):
    seen_max_tokens = []

    def fake_complete(messages, *, tools=None, prompt_version="v1", max_tokens=None, **kwargs):
        seen_max_tokens.append(max_tokens)
        return LLMResult(text="done", tool_calls=[])

    monkeypatch.setattr("app.llm.complete", fake_complete)

    run_tool_loop([{"role": "user", "content": "hi"}], tools=[], tool_impls={}, max_tokens=42)

    assert seen_max_tokens == [42]

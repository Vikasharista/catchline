"""Regression test: run_tool_loop must reconstruct the assistant message's
tool_calls in the OpenAI/litellm-expected shape ({"type": "function",
"function": {"name", "arguments"}}), not the flat LLMResult.tool_calls
format — otherwise a second loop iteration sends a malformed message and
Anthropic (via litellm) rejects it with a tool_use_id mismatch. Caught by
manual live testing; see app/llm.py history.
"""
import json

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

"""Single choke point for every LLM call in Catchline.

Per CLAUDE.md: all LLM calls go through this module. Model name is a config
setting (swappable via LLM_MODEL / LLM_FALLBACK env vars), never hardcoded.
Nothing here computes a number that gets displayed — that lives in
app/normalize/. This module only talks to the model and returns what it said.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import litellm

from app.config import settings

logger = logging.getLogger("catchline.llm")

_CALL_LOG_PATH = settings.data_dir / "llm_calls.jsonl"


@dataclass
class LLMResult:
    text: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None
    model: str = ""
    cached: bool = False


def _cache_path(cache_key: str) -> Path:
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
    return settings.llm_cache_dir / f"{digest}.json"


# Client errors (bad request, auth, billing, not found) won't succeed on a
# blind retry of the same request — only back off and retry on errors that
# plausibly resolve themselves (rate limits, transient server/network
# issues). Anything not recognized here is treated as retryable, since
# failing to retry a genuinely transient error is worse than one wasted
# retry on a genuinely permanent one.
_NON_RETRYABLE_EXCEPTION_TYPES = tuple(
    exc_type
    for exc_type in (
        getattr(litellm, "BadRequestError", None),
        getattr(litellm, "AuthenticationError", None),
        getattr(litellm, "PermissionDeniedError", None),
        getattr(litellm, "NotFoundError", None),
        getattr(litellm, "UnprocessableEntityError", None),
    )
    if exc_type is not None
)


def _is_retryable(exc: Exception) -> bool:
    return not isinstance(exc, _NON_RETRYABLE_EXCEPTION_TYPES)


def _log_call(model: str, messages: list[dict], latency_ms: float, cached: bool, prompt_version: str) -> None:
    entry = {
        "ts": time.time(),
        "model": model,
        "latency_ms": round(latency_ms, 1),
        "cached": cached,
        "prompt_version": prompt_version,
        "n_messages": len(messages),
    }
    with open(_CALL_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def complete(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
    cache_key: str | None = None,
    live: bool = False,
    prompt_version: str = "v1",
    max_retries: int = 2,
    max_tokens: int = 8192,
) -> LLMResult:
    """Call the configured LLM once.

    - `cache_key`: if set and `live` is False, reuses a prior response for the
      same key (used by extraction: sha256(file) + prompt_version + model).
    - Retries with backoff, then falls back to LLM_FALLBACK if configured.
    - `response_format` follows the OpenAI/LiteLLM json_schema shape for
      structured output.
    - `max_tokens` defaults well above litellm's provider default (4096):
      a truncated structured-output generation can come back as an empty
      but schema-valid stub instead of an error, which silently looks like
      a successful call with nothing in it.
    """
    full_cache_key = None
    if cache_key:
        full_cache_key = f"{settings.llm_model}:{prompt_version}:{cache_key}"
        path = _cache_path(full_cache_key)
        if not live and path.exists():
            data = json.loads(path.read_text())
            return LLMResult(
                text=data.get("text"),
                tool_calls=data.get("tool_calls", []),
                raw=data,
                model=settings.llm_model,
                cached=True,
            )

    models_to_try = [settings.llm_model]
    if settings.llm_fallback:
        models_to_try.append(settings.llm_fallback)

    last_error: Exception | None = None
    for model in models_to_try:
        for attempt in range(max_retries + 1):
            try:
                start = time.time()
                kwargs: dict[str, Any] = dict(
                    model=model,
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=max_tokens,
                )
                if tools:
                    kwargs["tools"] = tools
                if response_format:
                    kwargs["response_format"] = response_format

                response = litellm.completion(**kwargs)
                latency_ms = (time.time() - start) * 1000

                choice = response.choices[0]
                text = choice.message.content
                tool_calls = []
                if getattr(choice.message, "tool_calls", None):
                    for tc in choice.message.tool_calls:
                        tool_calls.append(
                            {
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": json.loads(tc.function.arguments or "{}"),
                            }
                        )

                _log_call(model, messages, latency_ms, cached=False, prompt_version=prompt_version)

                result = LLMResult(text=text, tool_calls=tool_calls, raw=response, model=model)

                if full_cache_key:
                    _cache_path(full_cache_key).write_text(
                        json.dumps({"text": text, "tool_calls": tool_calls})
                    )
                return result
            except Exception as exc:  # noqa: BLE001 - genuinely want to retry any provider error
                last_error = exc
                logger.warning("LLM call failed (model=%s attempt=%s): %s", model, attempt, exc)
                # A 4xx (bad request, auth, billing) won't fix itself on
                # retry — burning the retry budget on it just delays
                # falling back to the next model. Only back off and retry
                # on errors that plausibly are transient (5xx, timeouts,
                # rate limits).
                if not _is_retryable(exc):
                    break
                if attempt < max_retries:
                    time.sleep(2**attempt)
        # move on to fallback model
    raise RuntimeError(f"All LLM attempts failed: {last_error}") from last_error


def run_tool_loop(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_impls: dict[str, Callable[..., Any]],
    *,
    max_steps: int = 6,
    prompt_version: str = "v1",
) -> tuple[str, list[dict[str, Any]]]:
    """Runs a tool-calling loop and returns (final_text, transcript_of_tool_calls).

    Used by the co-pilot and analyst agents. Stops after max_steps to bound
    latency and cost; the caller decides what to do if it never finishes.
    """
    transcript: list[dict[str, Any]] = []
    working_messages = list(messages)

    for _ in range(max_steps):
        result = complete(working_messages, tools=tools, prompt_version=prompt_version)

        if not result.tool_calls:
            return result.text or "", transcript

        working_messages.append(
            {
                "role": "assistant",
                "content": result.text,
                "tool_calls": [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
                    }
                    for call in result.tool_calls
                ],
            }
        )

        for call in result.tool_calls:
            fn = tool_impls.get(call["name"])
            if fn is None:
                tool_result = {"error": f"unknown tool {call['name']}"}
            else:
                tool_result = fn(**call["arguments"])
            transcript.append({"tool": call["name"], "arguments": call["arguments"], "result": tool_result})
            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(tool_result, default=str),
                }
            )

    return "I ran out of steps working on that — could you rephrase or split the question?", transcript

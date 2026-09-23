"""Credit-wastage guardrail: once today's estimated spend hits
LLM_DAILY_BUDGET_USD, complete() must raise before attempting any further
real call — not just log a warning after the fact.
"""
import litellm
import pytest

import app.llm as llm_module
from app.llm import BudgetExceededError, _estimate_cost_usd, complete, get_budget_status


@pytest.fixture
def isolated_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_module, "_BUDGET_PATH", tmp_path / "llm_budget.json")
    monkeypatch.setattr(llm_module.settings, "llm_daily_budget_usd", 0.01)
    monkeypatch.setattr(llm_module.settings, "llm_model", "anthropic/claude-sonnet-4-5")
    monkeypatch.setattr(llm_module.settings, "llm_fallback", None)


def test_estimate_cost_uses_model_price_table():
    class Usage:
        prompt_tokens = 1_000_000
        completion_tokens = 1_000_000

    cost = _estimate_cost_usd("anthropic/claude-sonnet-4-5", Usage())
    assert cost == pytest.approx(3.00 + 15.00)


def test_estimate_cost_falls_back_for_unknown_model():
    class Usage:
        prompt_tokens = 1_000_000
        completion_tokens = 0

    cost = _estimate_cost_usd("some/unlisted-model", Usage())
    assert cost == pytest.approx(5.00)  # _DEFAULT_PRICE_PER_M_TOKENS[0]


def test_budget_status_starts_at_zero(isolated_budget):
    status = get_budget_status()
    assert status["spent_usd"] == 0.0
    assert status["calls_today"] == 0
    assert status["remaining_usd"] == pytest.approx(0.01)


def test_complete_raises_budget_exceeded_without_calling_litellm(isolated_budget, monkeypatch):
    # Record enough spend to blow through the $0.01 test budget first.
    llm_module._record_spend("anthropic/claude-sonnet-4-5", type("U", (), {"prompt_tokens": 1_000_000, "completion_tokens": 0})())

    def fail_if_called(**kwargs):
        raise AssertionError("litellm.completion should never be called once over budget")

    monkeypatch.setattr(litellm, "completion", fail_if_called)

    with pytest.raises(BudgetExceededError):
        complete([{"role": "user", "content": "hi"}])


def test_successful_call_records_spend(isolated_budget, monkeypatch):
    class FakeChoice:
        class message:
            content = "ok"
            tool_calls = None

    class FakeUsage:
        prompt_tokens = 100
        completion_tokens = 50

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: FakeResponse())

    complete([{"role": "user", "content": "hi"}])

    status = get_budget_status()
    assert status["calls_today"] == 1
    assert status["spent_usd"] > 0


def test_cached_response_never_checks_budget(isolated_budget, tmp_path, monkeypatch):
    # Blow the budget first...
    llm_module._record_spend("anthropic/claude-sonnet-4-5", type("U", (), {"prompt_tokens": 1_000_000, "completion_tokens": 0})())

    # ...then seed a cache entry and confirm the cached path still returns,
    # never touching litellm or the budget check.
    monkeypatch.setattr(llm_module.settings, "llm_cache_dir", tmp_path)
    full_key = f"{llm_module.settings.llm_model}:v1:mykey"
    path = llm_module._cache_path(full_key)
    path.write_text('{"text": "cached answer", "tool_calls": []}')

    def fail_if_called(**kwargs):
        raise AssertionError("a cache hit should never reach litellm.completion")

    monkeypatch.setattr(litellm, "completion", fail_if_called)

    result = complete([{"role": "user", "content": "hi"}], cache_key="mykey", prompt_version="v1")
    assert result.text == "cached answer"
    assert result.cached is True

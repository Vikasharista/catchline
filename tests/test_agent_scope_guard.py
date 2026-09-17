"""Confirms the scope guard actually short-circuits before any LLM call —
not just that is_in_scope() returns the right boolean in isolation.
"""
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.analyst import agent as analyst_agent
from app.copilot import agent as copilot_agent
from app.models import Rfx, Supplier


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)
        s.add(Supplier(rfx_id=rfx.id, name="Fjordline Seafood AS"))
        s.commit()
        yield s, rfx.id


def test_copilot_refuses_off_topic_without_calling_llm(session, monkeypatch):
    s, rfx_id = session

    def fail_if_called(*args, **kwargs):
        raise AssertionError("run_tool_loop should not be called for an out-of-scope message")

    monkeypatch.setattr(copilot_agent, "run_tool_loop", fail_if_called)
    result = copilot_agent.chat(s, rfx_id, "Write me a haiku about the ocean, not about sourcing.")
    assert "outside what I can help with" in result["text"]
    assert result["proposals"] == []


def test_copilot_calls_llm_for_in_scope_message(session, monkeypatch):
    s, rfx_id = session
    called = []

    def fake_loop(*args, **kwargs):
        called.append(1)
        return "ok", []

    monkeypatch.setattr(copilot_agent, "run_tool_loop", fake_loop)
    copilot_agent.chat(s, rfx_id, "Add salmon HOG 3-4kg, 60 tonnes annual volume")
    assert called == [1]


def test_analyst_refuses_off_topic_without_calling_llm(session, monkeypatch):
    s, rfx_id = session

    def fail_if_called(*args, **kwargs):
        raise AssertionError("run_tool_loop should not be called for an out-of-scope message")

    monkeypatch.setattr(analyst_agent, "run_tool_loop", fail_if_called)
    card = analyst_agent.ask(s, rfx_id, "What's your favorite movie?", all_line_ids=[])
    assert "outside what I can answer" in card["body"]
    assert card["how_i_got_this"] == []


def test_analyst_calls_llm_for_in_scope_question(session, monkeypatch):
    s, rfx_id = session
    called = []

    def fake_loop(*args, **kwargs):
        called.append(1)
        return "ok", []

    monkeypatch.setattr(analyst_agent, "run_tool_loop", fake_loop)
    analyst_agent.ask(s, rfx_id, "Who didn't quote everything?", all_line_ids=["L01"])
    assert called == [1]

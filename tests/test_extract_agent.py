"""Regression test: a syntactically valid but empty extraction on a
document with real content must be retried, not accepted as-is (caught by
manual live testing — see app/extract/agent.py for the story).
"""
import json

from app.extract import agent as agent_module
from app.ingest.router import Chunk, IngestedDoc

DOC = IngestedDoc(filename="test.xlsx", kind="xlsx", chunks=[Chunk(kind="table", content="A1: 80,73 NOK/kg", locator="Sheet1")])


class FakeResult:
    def __init__(self, text):
        self.text = text


def test_retries_on_empty_items_then_succeeds(monkeypatch):
    responses = [
        FakeResult(json.dumps({"items": []})),
        FakeResult(json.dumps({"items": [{"raw_text": "x", "locator": "A1", "product_desc": "salmon", "price": 80.73}]})),
    ]

    def fake_complete(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(agent_module, "complete", fake_complete)
    extraction, needs_attention = agent_module.extract_pass_a(DOC, sha256="abc", rfx_context="")

    assert needs_attention is False
    assert len(extraction.items) == 1


def test_accepts_empty_items_on_last_attempt_rather_than_failing(monkeypatch):
    def fake_complete(*args, **kwargs):
        return FakeResult(json.dumps({"items": []}))

    monkeypatch.setattr(agent_module, "complete", fake_complete)
    extraction, needs_attention = agent_module.extract_pass_a(DOC, sha256="abc", rfx_context="")

    # Both attempts came back empty — accept the empty result rather than
    # discarding real (if sparse) output as a hard failure.
    assert needs_attention is False
    assert extraction.items == []


def test_empty_items_on_truly_empty_document_is_not_retried(monkeypatch):
    empty_doc = IngestedDoc(filename="blank.xlsx", kind="xlsx", chunks=[])
    calls = []

    def fake_complete(*args, **kwargs):
        calls.append(1)
        return FakeResult(json.dumps({"items": []}))

    monkeypatch.setattr(agent_module, "complete", fake_complete)
    extraction, needs_attention = agent_module.extract_pass_a(empty_doc, sha256="abc", rfx_context="")

    assert len(calls) == 1  # no retry wasted on a document with nothing to extract
    assert extraction.items == []

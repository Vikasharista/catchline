"""Diagnostic endpoint added after a real "Missing credentials" deploy
failure where the user had already set OPENAI_API_KEY on Render, redeployed,
and still got the same error — with no way to see from outside what the
running process actually resolved. Guards that it reports presence/shape
without ever leaking a full key value.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_reports_configured_model_and_masked_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "openai/gpt-4o")
    monkeypatch.setattr(settings, "llm_fallback", "openai/gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_api_key", "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890")

    resp = client.get("/api/admin/llm-status")
    assert resp.status_code == 200
    body = resp.json()

    assert body["llm_model"] == "openai/gpt-4o"
    assert body["llm_fallback"] == "openai/gpt-4o-mini"
    key_info = body["keys"]["OPENAI_API_KEY"]
    assert key_info["set"] is True
    assert key_info["length"] == 44
    # never the full key, only a short masked preview
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890" not in str(body)
    assert key_info["preview"] == "sk-pro...7890"


def test_reports_unset_key_as_not_set(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)

    resp = client.get("/api/admin/llm-status")
    key_info = resp.json()["keys"]["OPENAI_API_KEY"]
    assert key_info == {"set": False, "length": 0, "preview": None}

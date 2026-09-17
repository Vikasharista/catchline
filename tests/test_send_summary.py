import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_session
from app.main import app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_send_summary_blocked_before_signoff(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    client.post(f"/api/rfx/{rfx_id}/seed-reference")

    summary = client.get(f"/api/rfx/{rfx_id}/send-summary").json()
    assert summary["ready_to_send"] is False
    assert len(summary["blocking_reasons"]["not_signed_off"]) == 4
    assert len(summary["suppliers"]) == 5
    assert summary["line_count"] == 30


def test_send_summary_ready_after_all_sections_signed_off(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    client.post(f"/api/rfx/{rfx_id}/seed-reference")

    for section in ("scope", "lines", "questionnaire", "terms"):
        res = client.post(f"/api/rfx/{rfx_id}/sections/{section}/signoff", json={"signed_by": "buyer"})
        assert res.status_code == 200, res.json()

    summary = client.get(f"/api/rfx/{rfx_id}/send-summary").json()
    assert summary["ready_to_send"] is True
    assert summary["blocking_reasons"]["not_signed_off"] == []
    assert all(s["status"] == "signed_off" for s in summary["sections"])
    assert all(s["signed_by"] == "buyer" for s in summary["sections"])


def test_send_endpoint_still_blocks_when_not_ready(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    client.post(f"/api/rfx/{rfx_id}/seed-reference")

    res = client.post(f"/api/rfx/{rfx_id}/send")
    assert res.status_code == 400

"""The Inbox screen used to lose its document list on reload (never
re-fetched from the backend, only built from a simulate/upload response in
JS memory) and showed every reply as a bare filename regardless of
whether it was actually a spreadsheet, a photo, or an email. These test
the API surface the fixed frontend relies on: a real GET for the
document list, raw file bytes, and a structured .eml preview.
"""
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


@pytest.fixture
def rfx_with_docs(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    client.post(f"/api/rfx/{rfx_id}/inbox/simulate")
    return client, rfx_id


def test_document_list_is_empty_for_a_fresh_rfx(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    assert client.get(f"/api/rfx/{rfx_id}/documents").json() == []


def test_simulated_documents_are_listed_with_their_real_kind(rfx_with_docs):
    client, rfx_id = rfx_with_docs
    docs = client.get(f"/api/rfx/{rfx_id}/documents").json()
    kinds = {d["kind"] for d in docs}
    # the seed dataset includes an xlsx, pdf, docx, image, eml, and certs
    assert "image" in kinds
    assert "eml" in kinds
    assert "certificate" in kinds
    assert all(d["status"] == "received" for d in docs)


def test_document_file_serves_real_bytes(rfx_with_docs):
    client, rfx_id = rfx_with_docs
    docs = client.get(f"/api/rfx/{rfx_id}/documents").json()
    image_doc = next(d for d in docs if d["kind"] == "image")
    resp = client.get(f"/api/documents/{image_doc['id']}/file")
    assert resp.status_code == 200
    assert len(resp.content) > 1000  # a real jpg, not an empty/error body


def test_eml_document_preview_parses_from_to_subject_body(rfx_with_docs):
    client, rfx_id = rfx_with_docs
    docs = client.get(f"/api/rfx/{rfx_id}/documents").json()
    eml_doc = next(d for d in docs if d["kind"] == "eml")
    preview = client.get(f"/api/documents/{eml_doc['id']}/preview").json()
    assert preview["kind"] == "eml"
    assert "@" in preview["from"]
    assert preview["subject"]
    assert preview["body"]


def test_non_eml_document_preview_returns_kind_and_filename(rfx_with_docs):
    client, rfx_id = rfx_with_docs
    docs = client.get(f"/api/rfx/{rfx_id}/documents").json()
    image_doc = next(d for d in docs if d["kind"] == "image")
    preview = client.get(f"/api/documents/{image_doc['id']}/preview").json()
    assert preview == {"kind": "image", "filename": image_doc["filename"]}


def test_document_file_404s_for_unknown_id(client):
    resp = client.get("/api/documents/99999/file")
    assert resp.status_code == 404


def test_outbox_is_empty_before_send(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    assert client.get(f"/api/rfx/{rfx_id}/outbox").json() == {"messages": []}

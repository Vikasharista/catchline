"""Regression test for a real bug: clicking Accept/Exclude/Ask supplier on a
review-queue item flagged "unmatched_item" (an extracted line item that
never matched any RFx line, so pipeline.py never created a NormalizedQuote
for it) returned 400 "unknown or inapplicable action: accept" — the
handler required `quote` to be truthy for every action, and a flag with no
quote fell through to the generic else branch regardless of which action
was sent. Fixed by letting accept/exclude/ask_supplier resolve the flag
even with no quote to update, and giving `edit` (which genuinely needs a
quote to change a price on) its own clear error instead.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_session
from app.main import app
from app.models import ExtractedItem, Document, Flag, Rfx, Supplier


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def _unmatched_item_flag(engine):
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)

        supplier = Supplier(rfx_id=rfx.id, name="Fjordline Seafood AS")
        s.add(supplier)
        s.commit()
        s.refresh(supplier)

        document = Document(supplier_id=supplier.id, filename="quote.xlsx", kind="xlsx", sha256="x", path="/tmp/x")
        s.add(document)
        s.commit()
        s.refresh(document)

        extracted = ExtractedItem(
            document_id=document.id,
            fields_json={},
            raw_text="Frozen cod fillets, unknown grade",
            locator_json={},
            confidence=0.4,
            legibility="clear",
            matched_line_id=None,
        )
        s.add(extracted)
        s.commit()
        s.refresh(extracted)

        flag = Flag(
            entity_type="extracted_item",
            entity_id=extracted.id,
            code="unmatched_item",
            severity="info",
            message="Item did not match any RFx line",
        )
        s.add(flag)
        s.commit()
        s.refresh(flag)
        return flag.id


def test_accept_on_quoteless_flag_resolves_instead_of_400(client):
    c, engine = client
    flag_id = _unmatched_item_flag(engine)
    res = c.post(f"/api/review/{flag_id}/resolve", json={"action": "accept"})
    assert res.status_code == 200
    assert res.json() == {"flag_id": flag_id, "resolved": True}


def test_exclude_on_quoteless_flag_resolves(client):
    c, engine = client
    flag_id = _unmatched_item_flag(engine)
    res = c.post(f"/api/review/{flag_id}/resolve", json={"action": "exclude"})
    assert res.status_code == 200


def test_ask_supplier_on_quoteless_flag_resolves(client):
    c, engine = client
    flag_id = _unmatched_item_flag(engine)
    res = c.post(f"/api/review/{flag_id}/resolve", json={"action": "ask_supplier"})
    assert res.status_code == 200


def test_edit_on_quoteless_flag_gives_clear_error_not_generic_fallback(client):
    c, engine = client
    flag_id = _unmatched_item_flag(engine)
    res = c.post(f"/api/review/{flag_id}/resolve", json={"action": "edit", "value": 7.5, "reason": "corrected"})
    assert res.status_code == 400
    assert "normalized quote" in res.json()["detail"]


def test_truly_unknown_action_still_errors(client):
    c, engine = client
    flag_id = _unmatched_item_flag(engine)
    res = c.post(f"/api/review/{flag_id}/resolve", json={"action": "nonsense"})
    assert res.status_code == 400
    assert "unknown action" in res.json()["detail"]

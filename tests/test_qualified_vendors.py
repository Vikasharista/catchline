from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Eligibility, ExtractedItem, NormalizedQuote, PurchaseOrder, QaAnswer, Rfx, RfxVersion, Supplier
from app.schemas.draft import RfxDraft
from app.validate.service import qualified_vendors_table, suggest_vendors_from_history

DRAFT = RfxDraft(
    lines=[
        {
            "line_id": "L01",
            "species": "Atlantic salmon (farmed)",
            "form": "HOG, frozen",
            "grade": "2-3 kg",
            "annual_volume_kg": 1000,
        }
    ]
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)
        s.add(RfxVersion(rfx_id=rfx.id, version=1, draft_json=DRAFT.model_dump(), created_by="t", cause="seed"))

        sup1 = Supplier(rfx_id=rfx.id, name="Fjordline Seafood AS")
        sup2 = Supplier(rfx_id=rfx.id, name="Oceanis Trading SARL")
        s.add(sup1)
        s.add(sup2)
        s.commit()
        s.refresh(sup1)
        s.refresh(sup2)

        item1 = ExtractedItem(document_id=1, fields_json={}, raw_text="x", locator_json={}, confidence=1.0, legibility="clear", matched_line_id="L01")
        item2 = ExtractedItem(document_id=2, fields_json={}, raw_text="y", locator_json={}, confidence=1.0, legibility="clear", matched_line_id="L01")
        s.add(item1)
        s.add(item2)
        s.commit()
        s.refresh(item1)
        s.refresh(item2)

        s.add(NormalizedQuote(item_id=item1.id, supplier_id=sup1.id, line_id="L01", eur_kg_net_dap=7.25, steps_json=[], status="confirmed"))
        s.add(NormalizedQuote(item_id=item2.id, supplier_id=sup2.id, line_id="L01", eur_kg_net_dap=7.15, steps_json=[], status="confirmed"))

        s.add(Eligibility(supplier_id=sup1.id, status="eligible", blocked_lines_json=[]))
        s.add(Eligibility(supplier_id=sup2.id, status="not_eligible", blocked_lines_json=[]))

        s.add(QaAnswer(supplier_id=sup1.id, q_id="Q10", answer="MOQ 1 FTL (22t); lead time 10 days"))

        s.add(
            PurchaseOrder(
                po_number="PO-2024-1",
                supplier_id=sup1.id,
                species="Atlantic salmon (farmed)",
                form="HOG, frozen",
                grade="3-4 kg",
                quantity_kg=20000,
                price_eur_kg_net_dap=7.0,
                order_date=datetime(2024, 1, 1),
            )
        )
        s.commit()

        yield s, rfx.id, sup1.id, sup2.id


def test_qualified_vendors_marks_eligible_supplier_qualified(session):
    s, rfx_id, sup1_id, sup2_id = session
    rows = qualified_vendors_table(s, rfx_id)
    assert len(rows) == 2

    row1 = next(r for r in rows if r["supplier_id"] == sup1_id)
    assert row1["qualified"] is True
    assert row1["price_eur_kg_net_dap"] == 7.25
    assert row1["delivery_sla"] == "MOQ 1 FTL (22t); lead time 10 days"


def test_qualified_vendors_marks_not_eligible_supplier_unqualified(session):
    s, rfx_id, sup1_id, sup2_id = session
    rows = qualified_vendors_table(s, rfx_id)
    row2 = next(r for r in rows if r["supplier_id"] == sup2_id)
    assert row2["qualified"] is False
    assert row2["eligibility"] == "not_eligible"


def test_suggest_vendors_from_history(session):
    s, rfx_id, sup1_id, sup2_id = session
    suggestions = suggest_vendors_from_history(s, rfx_id)
    assert "L01" in suggestions
    assert suggestions["L01"][0]["supplier_id"] == sup1_id
    assert suggestions["L01"][0]["past_orders"] == 1

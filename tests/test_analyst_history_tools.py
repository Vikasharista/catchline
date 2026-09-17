from datetime import datetime

import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.analyst.tools import AnalystTools
from app.models import Certificate, PastRfxEvent, PurchaseOrder, Rfx, Supplier


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)

        sup1 = Supplier(rfx_id=rfx.id, name="Fjordline Seafood AS")
        sup2 = Supplier(rfx_id=rfx.id, name="Pacific Rim Seafoods Ltd")
        s.add(sup1)
        s.add(sup2)
        s.commit()
        s.refresh(sup1)
        s.refresh(sup2)

        s.add(Certificate(supplier_id=sup1.id, scheme="BRCGS", grade="AA", valid_until=datetime(2027, 3, 31)))
        s.add(
            PurchaseOrder(
                po_number="PO-2024-1001",
                supplier_id=sup1.id,
                species="Atlantic salmon (farmed)",
                form="HOG, frozen",
                grade="3-4 kg",
                quantity_kg=20000,
                price_eur_kg_net_dap=7.2,
                order_date=datetime(2024, 3, 1),
            )
        )
        s.add(
            PurchaseOrder(
                po_number="PO-2024-1002",
                supplier_id=sup2.id,
                species="Vannamei shrimp (farmed)",
                form="HLSO, raw, block frozen",
                grade="21/25 per lb",
                quantity_kg=15000,
                price_eur_kg_net_dap=8.9,
                order_date=datetime(2024, 5, 1),
            )
        )
        s.add(
            PastRfxEvent(
                rfx_number="RFQ-2024-FROZ-009",
                year=2024,
                awarded_supplier_id=sup1.id,
                species_json=["Atlantic salmon (farmed)"],
                total_spend_eur=1_000_000,
                closed_date=datetime(2024, 9, 30),
            )
        )
        s.commit()
        yield s


def _tools(session):
    return AnalystTools(pd.DataFrame(), all_line_ids=[], all_supplier_ids=[], session=session)


def test_past_orders_all(session):
    result = _tools(session).past_orders()
    assert result["count"] == 2


def test_past_orders_filtered_by_supplier(session):
    result = _tools(session).past_orders(supplier_name="Fjordline")
    assert result["count"] == 1
    assert result["orders"][0]["po_number"] == "PO-2024-1001"


def test_past_orders_filtered_by_species(session):
    result = _tools(session).past_orders(species="shrimp")
    assert result["count"] == 1
    assert result["orders"][0]["supplier"] == "Pacific Rim Seafoods Ltd"


def test_past_rfqs(session):
    result = _tools(session).past_rfqs()
    assert result["count"] == 1
    assert result["events"][0]["awarded_supplier"] == "Fjordline Seafood AS"


def test_certificates_filtered(session):
    result = _tools(session).certificates(supplier_name="Fjordline")
    assert result["count"] == 1
    assert result["certificates"][0]["scheme"] == "BRCGS"


def test_no_session_returns_empty_not_error():
    tools = AnalystTools(pd.DataFrame(), all_line_ids=[], all_supplier_ids=[], session=None)
    assert tools.past_orders() == {"orders": [], "note": "no DB session available"}
    assert tools.past_rfqs() == {"events": [], "note": "no DB session available"}
    assert tools.certificates() == {"certificates": [], "note": "no DB session available"}

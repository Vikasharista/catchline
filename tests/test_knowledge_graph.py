from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.knowledge.graph import build_entity_graph, is_in_scope
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

        supplier = Supplier(rfx_id=rfx.id, name="Fjordline Seafood AS", email="sales@fjordline.example")
        s.add(supplier)
        s.commit()
        s.refresh(supplier)

        s.add(Certificate(supplier_id=supplier.id, scheme="BRCGS", grade="AA"))
        s.add(
            PurchaseOrder(
                po_number="PO-2024-1001",
                supplier_id=supplier.id,
                species="Atlantic salmon (farmed)",
                form="HOG, frozen",
                grade="3-4 kg",
                quantity_kg=20000,
                price_eur_kg_net_dap=7.2,
                order_date=datetime(2024, 3, 1),
            )
        )
        s.add(
            PastRfxEvent(
                rfx_number="RFQ-2024-FROZ-009",
                year=2024,
                awarded_supplier_id=supplier.id,
                species_json=["Atlantic salmon (farmed)"],
                total_spend_eur=1_000_000,
                closed_date=datetime(2024, 9, 30),
            )
        )
        s.commit()
        yield s


def test_in_scope_for_known_supplier(session):
    graph = build_entity_graph(session)
    # deliberately avoids any generic domain word so only the entity match can pass it
    in_scope, reason = is_in_scope("Tell me more about Fjordline", graph)
    assert in_scope
    assert "fjordline" in reason


def test_in_scope_for_generic_domain_term(session):
    graph = build_entity_graph(session)
    in_scope, _ = is_in_scope("What's the payment terms for this supplier?", graph)
    assert in_scope


def test_in_scope_for_cert_scheme(session):
    graph = build_entity_graph(session)
    in_scope, _ = is_in_scope("Is their BRCGS certificate still valid?", graph)
    assert in_scope


def test_in_scope_for_po_number(session):
    graph = build_entity_graph(session)
    in_scope, _ = is_in_scope("What's the status of PO-2024-1001?", graph)
    assert in_scope


def test_out_of_scope_for_unrelated_question(session):
    graph = build_entity_graph(session)
    in_scope, reason = is_in_scope("What's the weather like in Paris today?", graph)
    assert not in_scope
    assert "no recognized" in reason


def test_out_of_scope_for_general_coding_question(session):
    graph = build_entity_graph(session)
    in_scope, _ = is_in_scope("Can you write me a Python quicksort implementation?", graph)
    assert not in_scope


def test_in_scope_for_draft_line_species(session):
    graph = build_entity_graph(session, draft_lines=[{"line_id": "L17", "species": "Vannamei shrimp (farmed)"}])
    in_scope, reason = is_in_scope("Tell me about L17", graph)
    assert in_scope
    assert "l17" in reason

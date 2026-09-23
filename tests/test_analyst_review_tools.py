"""Regression tests for the four analyst tools added to answer 'review
before awarding' questions: questionnaire_answers (supplier-level), rfx_summary
(RFQ-level), sku_breakdown (SKU-wise price/quantity), and location_breakdown.
All back onto real data already in the schema (QaAnswer rows from real
document extraction, the draft's own scope/terms, real quotes, and real
extracted incoterm/incoterm_place fields plus the real buyer freight-adder
reference CSV) — nothing fabricated.
"""
import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.analyst.tools import AnalystTools
from app.models import Document, ExtractedItem, QaAnswer, Rfx, RfxVersion, Supplier
from app.schemas.draft import Line, Question, RfxDraft, Scope, Terms

DRAFT = RfxDraft(
    scope=Scope(title="Frozen seafood", incoterm="DAP", incoterm_place="Boulogne", buyer_site="Nordcap"),
    lines=[Line(line_id="L01", species="salmon", form="fillet", grade="A", annual_volume_kg=48000)],
    questionnaire=[
        Question(q_id="Q1", group="certifications", text="Do you hold BRCGS?", answer_type="yes_no"),
        Question(q_id="Q2", group="quality", text="What is your glaze %?", answer_type="text"),
    ],
    terms=Terms(payment_terms="30 days"),
)

QUOTES_COLUMNS = [
    "line_id",
    "species",
    "form",
    "grade",
    "volume_kg",
    "supplier_id",
    "supplier_name",
    "eur_kg_net_dap",
    "status",
    "eligibility",
    "line_blocked",
]


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
        sup2 = Supplier(rfx_id=rfx.id, name="Pacific Rim Seafoods Ltd")
        s.add(sup1)
        s.add(sup2)
        s.commit()
        s.refresh(sup1)
        s.refresh(sup2)

        s.add(QaAnswer(supplier_id=sup1.id, q_id="Q1", answer="Yes, valid to 2027", result="pass"))
        s.add(QaAnswer(supplier_id=sup1.id, q_id="Q2", answer="3%", result="pass"))
        # sup2 leaves Q2 unanswered

        doc = Document(supplier_id=sup1.id, filename="quote.xlsx", kind="xlsx", sha256="x", path="/tmp/x")
        s.add(doc)
        s.commit()
        s.refresh(doc)
        s.add(
            ExtractedItem(
                document_id=doc.id,
                fields_json={"incoterm": "FCA", "incoterm_place": "Alesund"},
                raw_text="",
                locator_json={},
                confidence=1.0,
                legibility="clear",
            )
        )
        s.commit()
        yield s, rfx.id, sup1.id, sup2.id


def _quotes_df():
    rows = [
        ("L01", "salmon", "fillet", "A", 48000, "S1", "Fjordline Seafood AS", 8.20, "confirmed", "eligible", False),
        ("L01", "salmon", "fillet", "A", 48000, "S2", "Pacific Rim Seafoods Ltd", 8.95, "confirmed", "eligible", False),
    ]
    return pd.DataFrame(rows, columns=QUOTES_COLUMNS)


def _tools(session, rfx_id):
    return AnalystTools(_quotes_df(), all_line_ids=["L01"], all_supplier_ids=["S1", "S2"], session=session, rfx_id=rfx_id)


def test_questionnaire_answers_filters_by_supplier_and_flags_unanswered(session):
    s, rfx_id, sup1_id, sup2_id = session
    result = _tools(s, rfx_id).questionnaire_answers()
    assert result["count"] == 2
    assert any(a["question"] == "Do you hold BRCGS?" for a in result["answers"])
    assert {u["supplier"] for u in result["unanswered"]} == {"Pacific Rim Seafoods Ltd"}


def test_questionnaire_answers_filtered_by_supplier_name(session):
    s, rfx_id, *_ = session
    result = _tools(s, rfx_id).questionnaire_answers(supplier_name="Fjordline")
    assert result["count"] == 2
    assert all(a["supplier"] == "Fjordline Seafood AS" for a in result["answers"])


def test_rfx_summary_exposes_real_draft_scope_and_terms(session):
    s, rfx_id, *_ = session
    result = _tools(s, rfx_id).rfx_summary()
    assert result["scope"]["incoterm"] == "DAP"
    assert result["scope"]["incoterm_place"] == "Boulogne"
    assert result["terms"]["payment_terms"] == "30 days"
    assert result["line_count"] == 1
    assert result["questionnaire_count"] == 2


def test_sku_breakdown_ranks_offers_and_computes_implied_spend(session):
    s, rfx_id, *_ = session
    result = _tools(s, rfx_id).sku_breakdown(line_id="L01")
    assert len(result["lines"]) == 1
    line = result["lines"][0]
    assert line["requested_volume_kg"] == 48000
    assert line["offers"][0]["supplier_name"] == "Fjordline Seafood AS"
    assert line["offers"][0]["implied_spend_eur"] == pytest.approx(8.20 * 48000)


def test_location_breakdown_uses_real_extracted_incoterm_and_freight_adder(session):
    s, rfx_id, *_ = session
    result = _tools(s, rfx_id).location_breakdown()
    fjordline = next(row for row in result["suppliers"] if row["supplier"] == "Fjordline Seafood AS")
    assert fjordline["stated_origins"] == ["FCA Alesund"]
    assert fjordline["freight_adders_eur_kg"]["FCA Alesund"] == pytest.approx(0.35)
    pacific = next(row for row in result["suppliers"] if row["supplier"] == "Pacific Rim Seafoods Ltd")
    assert pacific["stated_origins"] == []
    assert result["delivery_terms"]["incoterm"] == "DAP"


def test_no_session_returns_empty_not_error():
    tools = AnalystTools(pd.DataFrame(), all_line_ids=[], all_supplier_ids=[], session=None)
    assert tools.questionnaire_answers() == {"answers": [], "unanswered": [], "note": "no DB session available"}
    assert tools.rfx_summary() == {"note": "no DB session available"}
    assert tools.location_breakdown() == {"suppliers": [], "note": "no DB session available"}

"""Regression coverage for the previously-missing persistence: extraction's
questionnaire answers and certificate extraction now actually land in the
DB, and eligibility gets recomputed from real rows — not just left as
untested code (all three existed but nothing wired them together before
the "qualified vendors" feature needed them).
"""
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.pipeline as pipeline_module
from app.models import Certificate, Document, QaAnswer, Rfx, RfxVersion, Supplier
from app.schemas.certificate import CertificateExtraction
from app.schemas.draft import RfxDraft
from app.schemas.extraction import DocumentExtraction, ExtractedItem, QuestionnaireAnswer
from app.validate.service import compute_and_persist_eligibility


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)

        supplier = Supplier(rfx_id=rfx.id, name="Fjordline Seafood AS")
        s.add(supplier)
        s.commit()
        s.refresh(supplier)

        draft = RfxDraft(
            scope={"award_date": "2026-09-30"},
            lines=[
                {
                    "line_id": "L01",
                    "species": "Atlantic salmon (farmed)",
                    "form": "HOG, frozen",
                    "grade": "2-3 kg",
                    "annual_volume_kg": 1000,
                }
            ],
            terms={
                "award_rules": [
                    {"type": "require_valid_cert", "schemes": ["BRCGS", "IFS"]},
                ]
            },
        )
        s.add(RfxVersion(rfx_id=rfx.id, version=1, draft_json=draft.model_dump(), created_by="test", cause="seed"))
        s.commit()

        yield s, rfx.id, supplier.id


def test_questionnaire_answers_persisted(session, monkeypatch, tmp_path):
    s, rfx_id, supplier_id = session
    file_path = tmp_path / "s1.xlsx"
    file_path.write_bytes(b"fake xlsx bytes")
    document = Document(supplier_id=supplier_id, filename="s1.xlsx", kind="xlsx", sha256="abc", path=str(file_path))
    s.add(document)
    s.commit()
    s.refresh(document)

    extraction = DocumentExtraction(
        currency="EUR",
        items=[ExtractedItem(raw_text="x", locator="A1", product_desc="salmon", price=7.0, currency="EUR", price_unit="per_kg")],
        questionnaire_answers=[
            QuestionnaireAnswer(q_id="Q01", answer="BRCGS AA", raw_text="BRCGS AA, valid 2027", locator="Q1"),
        ],
    )

    from app.schemas.extraction import LineMatch, LineMatchResult

    monkeypatch.setattr(
        pipeline_module,
        "extract_pass_a",
        lambda doc, sha256, rfx_context, live=False: (extraction, False),
    )
    monkeypatch.setattr(
        pipeline_module,
        "extract_pass_b",
        lambda extraction, rfx_lines, sha256, live=False: LineMatchResult(
            matches=[LineMatch(item_index=0, line_id="L01", match_reason="species match", match_confidence=0.9)]
        ),
    )
    monkeypatch.setattr(pipeline_module, "route", lambda path: __import__("app.ingest.router", fromlist=["IngestedDoc"]).IngestedDoc(filename="s1.xlsx", kind="xlsx", chunks=[]))

    pipeline_module.process_document(s, document, live=False)

    answers = s.exec(select(QaAnswer).where(QaAnswer.supplier_id == supplier_id)).all()
    assert len(answers) == 1
    assert answers[0].q_id == "Q01"
    assert answers[0].answer == "BRCGS AA"


def test_certificate_extraction_persisted(session, monkeypatch, tmp_path):
    s, rfx_id, supplier_id = session
    file_path = tmp_path / "cert.pdf"
    file_path.write_bytes(b"fake pdf bytes")
    document = Document(supplier_id=supplier_id, filename="cert.pdf", kind="certificate", sha256="def", path=str(file_path))
    s.add(document)
    s.commit()
    s.refresh(document)

    cert_extraction = CertificateExtraction(scheme="BRCGS", grade="AA", certificate_no="CB-1", valid_until="2027-03-31")

    monkeypatch.setattr(pipeline_module, "extract_certificate", lambda doc, sha256, live=False: cert_extraction)
    monkeypatch.setattr(pipeline_module, "route", lambda path: __import__("app.ingest.router", fromlist=["IngestedDoc"]).IngestedDoc(filename="cert.pdf", kind="pdf", chunks=[]))

    pipeline_module.process_certificate_document(s, document, live=False)

    certs = s.exec(select(Certificate).where(Certificate.supplier_id == supplier_id)).all()
    assert len(certs) == 1
    assert certs[0].scheme == "BRCGS"
    assert certs[0].valid_until == datetime(2027, 3, 31)


def test_eligibility_computed_from_persisted_cert_and_qa(session):
    s, rfx_id, supplier_id = session
    s.add(QaAnswer(supplier_id=supplier_id, q_id="Q01", answer="BRCGS AA valid to 2027-03-31"))
    s.add(Certificate(supplier_id=supplier_id, scheme="BRCGS", grade="AA", valid_until=datetime(2027, 3, 31)))
    s.commit()

    results = compute_and_persist_eligibility(s, rfx_id)

    assert len(results) == 1
    assert results[0].status == "eligible"

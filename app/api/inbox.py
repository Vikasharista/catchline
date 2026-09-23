from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.api.deps import get_session
from app.channel.eml_preview import parse_eml_file
from app.channel.inbox import copy_to_inbox, guess_supplier, list_seed_files, save_upload
from app.events import emit
from app.models import AuditLog, Document, ExtractedItem, Supplier
from app.pipeline import process_certificate_document, process_document

router = APIRouter(prefix="/api")

EXT_TO_KIND = {".xlsx": "xlsx", ".pdf": "pdf", ".docx": "docx", ".jpg": "image", ".jpeg": "image", ".png": "image", ".eml": "eml"}


def _register_document(session: Session, rfx_id: int, path: Path) -> Document | None:
    supplier_name = guess_supplier(path.name)
    supplier = None
    if supplier_name:
        supplier = session.exec(
            select(Supplier).where(Supplier.rfx_id == rfx_id, Supplier.name == supplier_name)
        ).first()
    if supplier is None:
        return None  # caller must ask the buyer to pick a supplier

    is_certificate = path.name.endswith("food_safety_certificate.pdf")
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    doc = Document(
        supplier_id=supplier.id,
        filename=path.name,
        kind="certificate" if is_certificate else EXT_TO_KIND.get(path.suffix.lower(), "unknown"),
        sha256=sha256,
        path=str(path),
    )
    session.add(doc)
    session.add(AuditLog(actor="system", action="document_received", entity=f"document:{path.name}"))
    session.commit()
    session.refresh(doc)
    return doc


@router.post("/rfx/{rfx_id}/inbox/simulate")
def simulate_inbox(rfx_id: int, session: Session = Depends(get_session)):
    created = []
    unmatched = []
    for src in list_seed_files():
        dest = copy_to_inbox(src)
        doc = _register_document(session, rfx_id, dest)
        if doc is None:
            unmatched.append(dest.name)
        else:
            created.append({"id": doc.id, "filename": doc.filename, "supplier_id": doc.supplier_id, "kind": doc.kind})
            emit("doc_received", {"document_id": doc.id, "filename": doc.filename, "supplier_id": doc.supplier_id})
    return {"documents": created, "unmatched": unmatched}


@router.post("/rfx/{rfx_id}/inbox/upload")
async def upload_document(rfx_id: int, file: UploadFile, session: Session = Depends(get_session)):
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "file exceeds 20 MB limit")
    dest = save_upload(file.filename, content)
    doc = _register_document(session, rfx_id, dest)
    if doc is None:
        return {"needs_supplier_pick": True, "filename": dest.name}
    return {"id": doc.id, "filename": doc.filename, "supplier_id": doc.supplier_id}


@router.get("/rfx/{rfx_id}/documents")
def list_documents(rfx_id: int, session: Session = Depends(get_session)):
    """All documents received for this RFx so far — the Inbox screen was
    losing this on reload/navigation (only ever built from the JS response
    of simulate/upload calls, never re-fetched), the same class of bug the
    chat panel had before it got a history endpoint.
    """
    supplier_ids = [s.id for s in session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()]
    if not supplier_ids:
        return []
    docs = session.exec(
        select(Document).where(Document.supplier_id.in_(supplier_ids)).order_by(Document.received_at)
    ).all()
    result = []
    for d in docs:
        item_count = len(session.exec(select(ExtractedItem).where(ExtractedItem.document_id == d.id)).all())
        result.append(
            {
                "id": d.id,
                "filename": d.filename,
                "supplier_id": d.supplier_id,
                "kind": d.kind,
                "status": d.status,
                "item_count": item_count,
                "received_at": d.received_at,
            }
        )
    return result


@router.get("/documents/{document_id}/file")
def document_file(document_id: int, session: Session = Depends(get_session)):
    """Raw bytes of a received document — lets the Inbox screen render an
    image inline and offer a real "open" link for PDF/docx/xlsx/eml,
    instead of showing only a filename and a status badge.
    """
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "document not found")
    path = Path(document.path)
    if not path.exists():
        raise HTTPException(404, "file missing on disk")
    return FileResponse(path, filename=document.filename)


@router.get("/documents/{document_id}/preview")
def document_preview(document_id: int, session: Session = Depends(get_session)):
    """Structured preview for the Inbox screen: a parsed From/To/Subject/
    body for a .eml reply (so it renders as an actual email, not a
    filename), or just the kind/filename for other formats (rendered as an
    image, or a file link, by the frontend)."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "document not found")
    path = Path(document.path)
    if document.kind == "eml" and path.exists():
        return {"kind": "eml", **parse_eml_file(path)}
    return {"kind": document.kind, "filename": document.filename}


def _extract_one(session: Session, document: Document, *, live: bool) -> dict:
    if document.kind == "certificate":
        return process_certificate_document(session, document, live=live)
    return process_document(session, document, live=live)


def _rfx_id_for_document(session: Session, document: Document) -> int:
    supplier = session.get(Supplier, document.supplier_id)
    return supplier.rfx_id


@router.post("/documents/{document_id}/extract")
def extract_document(document_id: int, live: bool = False, session: Session = Depends(get_session)):
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "document not found")
    try:
        result = _extract_one(session, document, live=live)
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly error card, not a 500
        document.status = "needs_attention"
        session.add(document)
        session.commit()
        raise HTTPException(502, detail={"error": "Extraction failed", "message": str(exc), "retryable": True})

    from app.validate.service import compute_and_persist_eligibility

    compute_and_persist_eligibility(session, _rfx_id_for_document(session, document))
    return result


@router.post("/rfx/{rfx_id}/inbox/seed-and-extract-all")
def seed_and_extract_all(rfx_id: int, live: bool = False, session: Session = Depends(get_session)):
    """Convenience for the demo: simulates the inbox (all 5 replies + 4
    certificates) and extracts every document, so Review/Compare/Award have
    real data without clicking Extract nine times. Each document still goes
    through a real LLM call (or its cache) — nothing here is fabricated,
    it's just fewer clicks. One document's failure doesn't stop the rest.
    """
    simulate_result = simulate_inbox(rfx_id, session)

    extracted, failed = [], []
    for doc_summary in simulate_result["documents"]:
        document = session.get(Document, doc_summary["id"])
        try:
            result = _extract_one(session, document, live=live)
            extracted.append({"id": document.id, "filename": document.filename, **result})
        except Exception as exc:  # noqa: BLE001 - one bad document shouldn't stop the batch
            document.status = "needs_attention"
            session.add(document)
            session.commit()
            failed.append({"id": document.id, "filename": document.filename, "error": str(exc)})

    from app.validate.service import compute_and_persist_eligibility

    compute_and_persist_eligibility(session, rfx_id)

    return {
        "documents_registered": len(simulate_result["documents"]),
        "extracted": extracted,
        "failed": failed,
        "unmatched": simulate_result["unmatched"],
    }

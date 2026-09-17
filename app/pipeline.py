"""Wires ingest -> extract -> normalize -> validate together and persists
the result. This is the one place that turns a Document row into
ExtractedItem / NormalizedQuote / Flag rows in the DB.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from sqlmodel import Session, select

from app.copilot.tools import get_current_draft
from app.events import emit
from app.extract.agent import extract_pass_a, extract_pass_b
from app.ingest.router import route
from app.models import Document, ExtractedItem, Flag, NormalizedQuote, Supplier
from app.normalize.convert import NormalizeInput, convert
from app.schemas.draft import RfxDraft


def _rfx_context(draft: RfxDraft) -> tuple[str, list[dict]]:
    lines = [{"line_id": l.line_id, "species": l.species, "form": l.form, "grade": l.grade} for l in draft.lines]
    text = "\n".join(f"{l['line_id']}: {l['species']}, {l['form']}, {l['grade']}" for l in lines)
    return text, lines


def process_document(session: Session, document: Document, *, live: bool = False) -> dict:
    supplier = session.get(Supplier, document.supplier_id)
    rfx_id = supplier.rfx_id
    draft = RfxDraft.model_validate(get_current_draft(session, rfx_id))
    rfx_context, rfx_lines = _rfx_context(draft)

    path = Path(document.path)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    doc = route(path)
    emit("extract_step", {"document_id": document.id, "step": "opened"})

    extraction, needs_attention = extract_pass_a(doc, sha256=sha256, rfx_context=rfx_context, live=live)
    if extraction is None:
        document.status = "needs_attention"
        session.add(document)
        session.commit()
        emit("error", {"document_id": document.id, "message": "extraction failed"})
        return {"status": "needs_attention", "items": 0}
    emit("extract_step", {"document_id": document.id, "step": "found_prices", "n_items": len(extraction.items)})

    matches = extract_pass_b(extraction, rfx_lines, sha256=sha256, live=live)
    emit("extract_step", {"document_id": document.id, "step": "matched_lines"})
    match_by_item = {m.item_index: m for m in matches.matches}

    n_flags = 0
    for i, item in enumerate(extraction.items):
        match = match_by_item.get(i)
        line_id = match.line_id if match else None

        extracted_row = ExtractedItem(
            document_id=document.id,
            fields_json=item.model_dump(),
            raw_text=item.raw_text,
            locator_json={"locator": item.locator},
            confidence=item.confidence,
            legibility=item.legibility,
            matched_line_id=line_id,
            match_reason=match.match_reason if match else None,
            match_confidence=match.match_confidence if match else None,
        )
        session.add(extracted_row)
        session.commit()
        session.refresh(extracted_row)

        if line_id is None:
            session.add(
                Flag(
                    entity_type="extracted_item",
                    entity_id=extracted_row.id,
                    code="unmatched_item",
                    severity="info",
                    message=f"Item did not match any RFx line: {item.raw_text[:80]}",
                )
            )
            n_flags += 1
            continue

        norm_input = NormalizeInput(
            supplier_name=supplier.name,
            line_id=line_id,
            price=item.price,
            currency=item.currency or extraction.currency or "EUR",
            price_unit=item.price_unit or "per_kg",
            pack_size_kg=item.pack_size_kg,
            weight_basis=item.weight_basis,
            glaze_pct=item.glaze_pct,
            incoterm=item.incoterm or extraction.incoterm,
            incoterm_place=item.incoterm_place or extraction.incoterm_place,
            references_prior=item.references_prior,
        )
        result = convert(norm_input)

        status = "auto"
        if item.legibility == "illegible" or result.eur_kg_net_dap is None:
            status = "illegible"
        elif "inferred_prior" in result.flags:
            status = "inferred"

        quote = NormalizedQuote(
            item_id=extracted_row.id,
            supplier_id=document.supplier_id,
            line_id=line_id,
            eur_kg_net_dap=result.eur_kg_net_dap,
            steps_json=result.steps,
            status=status,
        )
        session.add(quote)

        for flag_code in result.flags:
            from app.validate.rules import severity_of

            session.add(
                Flag(
                    entity_type="normalized_quote",
                    entity_id=extracted_row.id,
                    code=flag_code,
                    severity=severity_of(flag_code),
                    message=f"{line_id}: {flag_code}",
                )
            )
            n_flags += 1

    document.status = "extracted"
    session.add(document)
    session.commit()
    emit("extract_step", {"document_id": document.id, "step": "converted"})
    if n_flags:
        emit("flag_created", {"document_id": document.id, "count": n_flags})
    emit("extract_step", {"document_id": document.id, "step": "checked"})

    return {"status": "extracted", "items": len(extraction.items), "flags": n_flags}

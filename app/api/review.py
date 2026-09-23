from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import AuditLog, ExtractedItem, Flag, NormalizedQuote

router = APIRouter(prefix="/api")


@router.get("/rfx/{rfx_id}/review")
def review_queue(rfx_id: int, session: Session = Depends(get_session)):
    flags = session.exec(select(Flag).where(Flag.resolved == False)).all()  # noqa: E712
    items = []
    for flag in flags:
        if flag.entity_type not in ("extracted_item", "normalized_quote"):
            continue
        extracted = session.get(ExtractedItem, flag.entity_id)
        if extracted is None:
            continue
        quote = session.exec(
            select(NormalizedQuote).where(NormalizedQuote.item_id == extracted.id)
        ).first()
        items.append(
            {
                "flag_id": flag.id,
                "code": flag.code,
                "severity": flag.severity,
                "message": flag.message,
                "raw_text": extracted.raw_text,
                "locator": extracted.locator_json,
                "line_id": extracted.matched_line_id,
                "eur_kg_net_dap": quote.eur_kg_net_dap if quote else None,
                "steps": quote.steps_json if quote else [],
                "status": quote.status if quote else None,
            }
        )
    return {"count": len(items), "items": items}


class ResolveBody(BaseModel):
    action: str  # accept | edit | ask_supplier | exclude | override
    value: float | None = None
    reason: str | None = None


@router.post("/review/{flag_id}/resolve")
def resolve_flag(flag_id: int, body: ResolveBody, session: Session = Depends(get_session)):
    flag = session.get(Flag, flag_id)
    if flag is None:
        raise HTTPException(404, "flag not found")

    extracted = session.get(ExtractedItem, flag.entity_id) if flag.entity_type in ("extracted_item", "normalized_quote") else None
    quote = (
        session.exec(select(NormalizedQuote).where(NormalizedQuote.item_id == extracted.id)).first()
        if extracted
        else None
    )

    # A flag with no NormalizedQuote (e.g. "unmatched_item": the item never matched
    # an RFx line, so no quote was ever normalized for it) has no price/status to
    # change — accept/exclude/ask_supplier still just resolve the flag itself.
    if body.action == "accept":
        if quote:
            quote.status = "confirmed"
            session.add(quote)
    elif body.action == "edit":
        if quote is None:
            raise HTTPException(400, "edit requires a normalized quote, and this flag has none")
        if body.value is None or not body.reason:
            raise HTTPException(400, "edit requires a value and a reason")
        quote.eur_kg_net_dap = body.value
        quote.status = "edited"
        session.add(quote)
    elif body.action == "exclude":
        if quote:
            quote.status = "excluded"
            session.add(quote)
    elif body.action == "ask_supplier":
        if quote:
            quote.status = "ask_supplier"
            session.add(quote)
    elif body.action == "override":
        pass  # eligibility overrides are handled via the eligibility record, not a flag
    else:
        raise HTTPException(400, f"unknown action: {body.action}")

    flag.resolved = True
    session.add(flag)
    session.add(
        AuditLog(
            actor="buyer",
            action=f"review_{body.action}",
            entity=f"flag:{flag_id}",
            after_json={"value": body.value},
            reason=body.reason,
        )
    )
    session.commit()
    return {"flag_id": flag_id, "resolved": True}

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.analyst.agent import ask as analyst_ask
from app.api.deps import get_session

router = APIRouter(prefix="/api")


class AskBody(BaseModel):
    question: str


@router.post("/rfx/{rfx_id}/analyst/messages")
def analyst_message(rfx_id: int, body: AskBody, session: Session = Depends(get_session)):
    from app.copilot.tools import get_current_draft
    from app.schemas.draft import RfxDraft

    draft = RfxDraft.model_validate(get_current_draft(session, rfx_id))
    all_line_ids = [l.line_id for l in draft.lines]
    try:
        return analyst_ask(session, rfx_id, body.question, all_line_ids)
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly error card, not a 500
        raise HTTPException(502, detail={"error": "Analyst is unavailable", "message": str(exc), "retryable": True})

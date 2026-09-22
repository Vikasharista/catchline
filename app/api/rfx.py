from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_session
from app.bootstrap import seed_new_rfx
from app.copilot import service
from app.copilot.agent import chat as copilot_chat
from app.copilot.tools import get_current_draft, get_pending_proposals, get_section_states
from app.exports.rfq_pdf import build_rfq_pdf
from app.exports.template_xlsx import build_template_xlsx
from app.models import AuditLog, ChangeProposal, ChatTurn, CopilotQuestion, Rfx, RfxVersion, SectionState, Supplier
from app.schemas.draft import RfxDraft

router = APIRouter(prefix="/api")


@router.post("/rfx")
def create_rfx(session: Session = Depends(get_session)):
    rfx = Rfx()
    session.add(rfx)
    session.commit()
    session.refresh(rfx)
    seed_new_rfx(session, rfx.id)
    return {"id": rfx.id}


@router.get("/rfx")
def list_rfx(session: Session = Depends(get_session)):
    """All RFQs, newest first — backs the RFx switcher so a buyer can start a
    new RFQ without losing the current one's chat and draft (still there,
    tied to its own rfx_id, never touched by starting a new one).
    """
    rows = session.exec(select(Rfx).order_by(Rfx.id.desc())).all()
    result = []
    for rfx in rows:
        draft = get_current_draft(session, rfx.id)
        result.append(
            {
                "id": rfx.id,
                "status": rfx.status,
                "title": (draft.get("scope") or {}).get("title") or f"RFX-{rfx.id}",
                "line_count": len(draft.get("lines", [])),
                "created_at": rfx.created_at,
            }
        )
    return result


@router.post("/rfx/{rfx_id}/seed-reference")
def seed_reference(rfx_id: int, session: Session = Depends(get_session)):
    """Kept for direct API use (tests, re-seeding an existing RFx) — new
    RFx creation seeds automatically now, see app.bootstrap.seed_new_rfx.
    """
    try:
        seed_new_rfx(session, rfx_id)
    except ValueError:
        raise HTTPException(404, "rfx not found")
    return {"version": 1}


def _serialize_proposal(p: ChangeProposal) -> dict:
    return {
        "id": p.id,
        "section": p.section_key,
        "op": p.op,
        "target": p.target,
        "value": (p.after_json or {}).get("value", p.after_json),
        "reason": p.reason,
        "origin": p.origin,
        "risk": p.risk,
        "status": p.status,
    }


@router.get("/rfx/{rfx_id}")
def get_rfx(rfx_id: int, session: Session = Depends(get_session)):
    rfx = session.get(Rfx, rfx_id)
    if rfx is None:
        raise HTTPException(404, "rfx not found")
    return {
        "id": rfx.id,
        "status": rfx.status,
        "draft": get_current_draft(session, rfx_id),
        "sections": get_section_states(session, rfx_id),
        "pending_proposals": [_serialize_proposal(p) for p in get_pending_proposals(session, rfx_id)],
    }


class ChatMessage(BaseModel):
    message: str


@router.get("/rfx/{rfx_id}/copilot/messages")
def copilot_history(rfx_id: int, session: Session = Depends(get_session)):
    """Chat history for the RFQ page's chat panel — was never fetched by the
    frontend before, so a reload or navigating away silently lost the whole
    conversation even though ChatTurn rows were there in the DB all along.
    Proposals a turn produced are attached inline (looked up by the
    preceding user turn's id, since that's what CopilotTools.chat_turn_id
    is set to) so the buyer can see what was suggested and its current
    accept/reject status without cross-referencing a separate list.
    """
    turns = session.exec(
        select(ChatTurn).where(ChatTurn.rfx_id == rfx_id, ChatTurn.thread == "copilot").order_by(ChatTurn.created_at)
    ).all()
    messages = []
    last_user_turn_id = None
    for t in turns:
        entry = {"id": t.id, "role": t.role, "content": t.content, "created_at": t.created_at, "proposals": []}
        if t.role == "user":
            last_user_turn_id = t.id
        elif last_user_turn_id is not None:
            proposals = session.exec(
                select(ChangeProposal).where(ChangeProposal.chat_turn_id == last_user_turn_id)
            ).all()
            entry["proposals"] = [_serialize_proposal(p) for p in proposals]
        messages.append(entry)
    return messages


@router.post("/rfx/{rfx_id}/copilot/messages")
def copilot_message(rfx_id: int, body: ChatMessage, session: Session = Depends(get_session)):
    try:
        result = copilot_chat(session, rfx_id, body.message)
    except Exception as exc:  # noqa: BLE001 - surfaced as a friendly error card, not a 500
        raise HTTPException(502, detail={"error": "Co-pilot is unavailable", "message": str(exc), "retryable": True})
    result["proposals"] = [
        _serialize_proposal(p)
        for pid in result["proposals"]
        if (p := session.get(ChangeProposal, pid)) is not None
    ]
    return result


@router.post("/proposals/{proposal_id}/accept")
def accept_proposal(proposal_id: int, session: Session = Depends(get_session)):
    try:
        proposal = service.accept_proposal(session, proposal_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": proposal.id, "status": proposal.status, "error": proposal.error}


class EditBody(BaseModel):
    value: object


@router.post("/proposals/{proposal_id}/edit")
def edit_proposal(proposal_id: int, body: EditBody, session: Session = Depends(get_session)):
    try:
        proposal = service.edit_proposal(session, proposal_id, body.value)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": proposal.id, "status": proposal.status, "error": proposal.error}


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, session: Session = Depends(get_session)):
    try:
        proposal = service.reject_proposal(session, proposal_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": proposal.id, "status": proposal.status}


class AcceptVisibleBody(BaseModel):
    ids: list[int]


@router.post("/rfx/{rfx_id}/proposals/accept-visible")
def accept_visible(rfx_id: int, body: AcceptVisibleBody, session: Session = Depends(get_session)):
    return service.accept_all_visible(session, rfx_id, body.ids)


class AnswerBody(BaseModel):
    answer: str


@router.post("/rfx/{rfx_id}/questions/{qid}/answer")
def answer_question(rfx_id: int, qid: int, body: AnswerBody, session: Session = Depends(get_session)):
    question = session.get(CopilotQuestion, qid)
    if question is None or question.rfx_id != rfx_id:
        raise HTTPException(404, "question not found")
    question.answer = body.answer
    question.answered_at = datetime.utcnow()
    session.add(question)
    session.commit()
    return {"id": question.id, "answer": question.answer}


class SignoffBody(BaseModel):
    signed_by: str = "buyer"


@router.post("/rfx/{rfx_id}/sections/{section_key}/signoff")
def signoff_section(rfx_id: int, section_key: str, body: SignoffBody, session: Session = Depends(get_session)):
    ok, failures = service.sign_off_section(session, rfx_id, section_key, body.signed_by)
    if not ok:
        raise HTTPException(400, detail={"failures": failures})
    return {"section": section_key, "status": "signed_off"}


@router.post("/rfx/{rfx_id}/sections/{section_key}/reopen")
def reopen_section(rfx_id: int, section_key: str, session: Session = Depends(get_session)):
    service.reopen_section(session, rfx_id, section_key, "buyer")
    return {"section": section_key, "status": "reopened"}


@router.get("/rfx/{rfx_id}/versions")
def list_versions(rfx_id: int, session: Session = Depends(get_session)):
    versions = session.exec(
        select(RfxVersion).where(RfxVersion.rfx_id == rfx_id).order_by(RfxVersion.version)
    ).all()
    return [{"version": v.version, "created_by": v.created_by, "cause": v.cause, "created_at": v.created_at} for v in versions]


@router.post("/rfx/{rfx_id}/versions/{version}/restore")
def restore_version(rfx_id: int, version: int, session: Session = Depends(get_session)):
    try:
        new_version = service.restore_version(session, rfx_id, version, "buyer")
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {"version": new_version.version}


@router.get("/rfx/{rfx_id}/preview/rfq.pdf")
def preview_rfq_pdf(rfx_id: int, session: Session = Depends(get_session)):
    draft = get_current_draft(session, rfx_id)
    pdf_bytes = build_rfq_pdf(draft)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/rfx/{rfx_id}/preview/template.xlsx")
def preview_template_xlsx(rfx_id: int, session: Session = Depends(get_session)):
    draft = get_current_draft(session, rfx_id)
    xlsx_bytes = build_template_xlsx(draft)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/rfx/{rfx_id}/send-summary")
def send_summary(rfx_id: int, session: Session = Depends(get_session)):
    """Pre-send review (PRD §7.2 step 8): sign-off summary, who/when, the
    supplier list an email will actually go to, and whether Send is unlocked
    yet — so the UI can show a confirm step instead of sending blind.
    """
    draft_dict = get_current_draft(session, rfx_id)
    draft = RfxDraft.model_validate(draft_dict)
    required = ["scope", "lines", "questionnaire", "terms"]

    states = session.exec(select(SectionState).where(SectionState.rfx_id == rfx_id)).all()
    state_by_key = {s.section_key: s for s in states}
    sections = [
        {
            "key": key,
            "status": state_by_key[key].status if key in state_by_key else "drafting",
            "signed_by": state_by_key[key].signed_by if key in state_by_key else None,
            "signed_at": state_by_key[key].signed_at if key in state_by_key else None,
        }
        for key in required
    ]

    pending = get_pending_proposals(session, rfx_id)
    not_signed = [s["key"] for s in sections if s["status"] != "signed_off"]
    suppliers = session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()

    return {
        "rfx_title": draft.scope.title,
        "sections": sections,
        "pending_proposal_count": len(pending),
        "suppliers": [{"name": s.name, "email": s.email} for s in suppliers],
        "line_count": len(draft.lines),
        "ready_to_send": not not_signed and not pending,
        "blocking_reasons": {"not_signed_off": not_signed, "pending_proposal_count": len(pending)},
    }


@router.post("/rfx/{rfx_id}/send")
def send_rfx(rfx_id: int, session: Session = Depends(get_session)):
    from app.channel.outbox import send_rfx_to_suppliers

    rfx = session.get(Rfx, rfx_id)
    if rfx is None:
        raise HTTPException(404, "rfx not found")

    draft_dict = get_current_draft(session, rfx_id)
    draft = RfxDraft.model_validate(draft_dict)
    sections = get_section_states(session, rfx_id)
    required = {"scope", "lines", "questionnaire", "terms"}
    not_signed = [s for s in required if sections.get(s) != "signed_off"]
    pending = get_pending_proposals(session, rfx_id)
    if not_signed or pending:
        raise HTTPException(400, detail={"not_signed_off": not_signed, "pending_proposal_count": len(pending)})

    pdf_bytes = build_rfq_pdf(draft_dict)
    xlsx_bytes = build_template_xlsx(draft_dict)
    suppliers = session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()
    paths = send_rfx_to_suppliers(
        [{"name": s.name, "email": s.email} for s in suppliers],
        pdf_bytes,
        xlsx_bytes,
        draft.scope.title or "RFQ",
    )

    rfx.status = "sent"
    session.add(rfx)
    session.add(AuditLog(actor="buyer", action="rfx_sent", entity=f"rfx:{rfx_id}", after_json={"emails": len(paths)}))
    session.commit()
    return {"status": "sent", "emails_written": len(paths)}

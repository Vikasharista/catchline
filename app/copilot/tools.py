"""Co-pilot agent tools (PRD §7.2). None of these write to the draft — they
only create change_proposal / copilot_question rows. copilot/apply.py is the
only code path that ever changes a draft, and only after a buyer clicks
Accept or Edit.
"""
from __future__ import annotations

import re
from typing import Any

from sqlmodel import Session, select

from app.events import emit
from app.models import ChangeProposal, CopilotQuestion, Rfx, RfxVersion, SectionState
from app.schemas.draft import RfxDraft, classify_risk

EMPTY_DRAFT = RfxDraft().model_dump()


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def get_current_draft(session: Session, rfx_id: int) -> dict:
    version = session.exec(
        select(RfxVersion).where(RfxVersion.rfx_id == rfx_id).order_by(RfxVersion.version.desc())
    ).first()
    return version.draft_json if version else dict(EMPTY_DRAFT)


def get_section_states(session: Session, rfx_id: int) -> dict[str, str]:
    states = session.exec(select(SectionState).where(SectionState.rfx_id == rfx_id)).all()
    return {s.section_key: s.status for s in states}


def get_pending_proposals(session: Session, rfx_id: int) -> list[ChangeProposal]:
    return session.exec(
        select(ChangeProposal).where(ChangeProposal.rfx_id == rfx_id, ChangeProposal.status == "pending")
    ).all()


def get_rejected_proposals(session: Session, rfx_id: int, limit: int = 20) -> list[ChangeProposal]:
    return session.exec(
        select(ChangeProposal)
        .where(ChangeProposal.rfx_id == rfx_id, ChangeProposal.status == "rejected")
        .order_by(ChangeProposal.decided_at.desc())
        .limit(limit)
    ).all()


class CopilotTools:
    def __init__(self, session: Session, rfx_id: int, chat_turn_id: int | None = None):
        self.session = session
        self.rfx_id = rfx_id
        self.chat_turn_id = chat_turn_id
        self.created_proposals: list[ChangeProposal] = []
        self.created_questions: list[CopilotQuestion] = []

    def read_draft(self) -> dict[str, Any]:
        draft = get_current_draft(self.session, self.rfx_id)
        sections = get_section_states(self.session, self.rfx_id)
        pending = get_pending_proposals(self.session, self.rfx_id)
        rejected = get_rejected_proposals(self.session, self.rfx_id)
        return {
            "draft": draft,
            "sections": sections,
            "pending_proposals": [
                {"section": p.section_key, "op": p.op, "target": p.target, "reason": p.reason} for p in pending
            ],
            "recently_rejected": [
                {"section": p.section_key, "op": p.op, "target": p.target, "reason": p.reason} for p in rejected
            ],
        }

    def propose_change(self, section: str, op: str, target: str, value: Any, reason: str, origin: str) -> dict:
        section_states = get_section_states(self.session, self.rfx_id)
        risk = classify_risk(section, target, op)
        status = "held" if section_states.get(section) == "signed_off" else "pending"

        proposal = ChangeProposal(
            rfx_id=self.rfx_id,
            chat_turn_id=self.chat_turn_id,
            section_key=section,
            op=op,
            target=target,
            after_json={"value": value} if not isinstance(value, dict) else value,
            reason=reason,
            origin=origin,
            risk=risk,
            status=status,
        )
        self.session.add(proposal)
        self.session.commit()
        self.session.refresh(proposal)
        self.created_proposals.append(proposal)
        emit("proposal_created", {"proposal_id": proposal.id, "section": section, "status": status, "risk": risk})
        return {"proposal_id": proposal.id, "status": status, "risk": risk}

    def propose_section(
        self, title: str, body_md: str, requires_supplier_response: bool, reason: str, origin: str
    ) -> dict:
        section_value = {
            "key": _slugify(title),
            "title": title,
            "body_md": body_md,
            "requires_supplier_response": requires_supplier_response,
        }
        return self.propose_change(
            section="custom_sections",
            op="add",
            target="custom_sections",
            value=section_value,
            reason=reason,
            origin=origin,
        )

    def ask(self, question: str, allow_free_text: bool, options: list[str] | None = None) -> dict:
        q = CopilotQuestion(
            rfx_id=self.rfx_id,
            chat_turn_id=self.chat_turn_id,
            question=question,
            options_json=options,
        )
        self.session.add(q)
        self.session.commit()
        self.session.refresh(q)
        self.created_questions.append(q)
        emit("question_created", {"question_id": q.id, "question": question})
        return {"question_id": q.id}

    def as_impls(self) -> dict[str, Any]:
        return {
            "read_draft": self.read_draft,
            "propose_change": self.propose_change,
            "propose_section": self.propose_section,
            "ask": self.ask,
        }

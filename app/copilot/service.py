"""Buyer-facing draft operations: accept/edit/reject a proposal, accept-all-
visible, section sign-off/reopen, version restore (PRD §7.2 steps 3-7).
The only code path that calls apply_patch — a proposal becomes a draft
change only through here, after a buyer action.
"""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.copilot.apply import apply_patch
from app.copilot.checks import run_check
from app.copilot.tools import get_current_draft
from app.models import AuditLog, ChangeProposal, RfxVersion, SectionState


def _next_version(session: Session, rfx_id: int) -> int:
    latest = session.exec(
        select(RfxVersion).where(RfxVersion.rfx_id == rfx_id).order_by(RfxVersion.version.desc())
    ).first()
    return (latest.version if latest else 0) + 1


def _save_version(session: Session, rfx_id: int, draft: dict, created_by: str, cause: str) -> RfxVersion:
    version = RfxVersion(
        rfx_id=rfx_id,
        version=_next_version(session, rfx_id),
        draft_json=draft,
        created_by=created_by,
        cause=cause,
    )
    session.add(version)
    session.add(AuditLog(actor=created_by, action="draft_version_saved", entity=f"rfx:{rfx_id}", after_json={"cause": cause}))
    session.commit()
    return version


def _apply_proposal(session: Session, proposal: ChangeProposal, value_override=None) -> tuple[bool, str | None]:
    draft = get_current_draft(session, proposal.rfx_id)
    value = value_override if value_override is not None else (proposal.after_json or {}).get("value", proposal.after_json)
    result = apply_patch(draft, proposal.section_key, proposal.op, proposal.target, value)
    if not result.ok:
        return False, result.error
    _save_version(session, proposal.rfx_id, result.draft, "buyer", f"proposal:{proposal.id}")
    return True, None


def accept_proposal(session: Session, proposal_id: int) -> ChangeProposal:
    proposal = session.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise ValueError("proposal not found")
    if proposal.status != "pending":
        raise ValueError(f"proposal is {proposal.status}, not pending")

    ok, error = _apply_proposal(session, proposal)
    proposal.decided_at = datetime.utcnow()
    if ok:
        proposal.status = "accepted"
    else:
        proposal.status = "failed"
        proposal.error = error
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def edit_proposal(session: Session, proposal_id: int, value) -> ChangeProposal:
    proposal = session.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise ValueError("proposal not found")
    if proposal.status != "pending":
        raise ValueError(f"proposal is {proposal.status}, not pending")

    ok, error = _apply_proposal(session, proposal, value_override=value)
    proposal.decided_at = datetime.utcnow()
    if ok:
        proposal.status = "edited"
        proposal.after_json = {"value": value}
    else:
        proposal.status = "failed"
        proposal.error = error
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def reject_proposal(session: Session, proposal_id: int) -> ChangeProposal:
    proposal = session.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise ValueError("proposal not found")
    proposal.status = "rejected"
    proposal.decided_at = datetime.utcnow()
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def accept_all_visible(session: Session, rfx_id: int, proposal_ids: list[int]) -> dict:
    accepted, skipped = [], []
    for pid in proposal_ids:
        proposal = session.get(ChangeProposal, pid)
        if proposal is None or proposal.rfx_id != rfx_id or proposal.status != "pending":
            continue
        if proposal.risk == "money_or_eligibility":
            skipped.append(pid)
            continue
        accept_proposal(session, pid)
        accepted.append(pid)
    return {"accepted": accepted, "skipped": skipped}


def sign_off_section(session: Session, rfx_id: int, section_key: str, signed_by: str) -> tuple[bool, list[str]]:
    draft_dict = get_current_draft(session, rfx_id)
    from app.schemas.draft import RfxDraft

    draft = RfxDraft.model_validate(draft_dict)
    failures = run_check(draft, section_key)
    if failures:
        return False, failures

    state = session.exec(
        select(SectionState).where(SectionState.rfx_id == rfx_id, SectionState.section_key == section_key)
    ).first()
    if state is None:
        state = SectionState(rfx_id=rfx_id, section_key=section_key)
    state.status = "signed_off"
    state.signed_by = signed_by
    state.signed_at = datetime.utcnow()
    state.last_check_json = {"failures": []}
    session.add(state)
    session.add(AuditLog(actor=signed_by, action="section_signed_off", entity=f"{rfx_id}:{section_key}"))
    session.commit()
    return True, []


def reopen_section(session: Session, rfx_id: int, section_key: str, actor: str) -> None:
    state = session.exec(
        select(SectionState).where(SectionState.rfx_id == rfx_id, SectionState.section_key == section_key)
    ).first()
    if state is None:
        state = SectionState(rfx_id=rfx_id, section_key=section_key)
    state.status = "reopened"
    session.add(state)

    held = session.exec(
        select(ChangeProposal).where(
            ChangeProposal.rfx_id == rfx_id,
            ChangeProposal.section_key == section_key,
            ChangeProposal.status == "held",
        )
    ).all()
    for proposal in held:
        proposal.status = "pending"
        session.add(proposal)

    session.add(AuditLog(actor=actor, action="section_reopened", entity=f"{rfx_id}:{section_key}"))
    session.commit()


def restore_version(session: Session, rfx_id: int, version_number: int, actor: str) -> RfxVersion:
    target = session.exec(
        select(RfxVersion).where(RfxVersion.rfx_id == rfx_id, RfxVersion.version == version_number)
    ).first()
    if target is None:
        raise ValueError("version not found")

    current = get_current_draft(session, rfx_id)
    new_version = _save_version(session, rfx_id, target.draft_json, actor, f"restore:{version_number}")

    # Reopen every section whose content differs between old and restored draft.
    for section_key in ("scope", "lines", "questionnaire", "terms"):
        if current.get(section_key) != target.draft_json.get(section_key):
            reopen_section(session, rfx_id, section_key, actor)

    return new_version

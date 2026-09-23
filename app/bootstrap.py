"""Seeding for a freshly created RFx.

A new RFx gets its supplier address book and synthetic purchase history
(scripts/seed_history.py) automatically, but the draft itself starts
empty — the co-pilot builds it up through chat, asking the buyer for
scope/lines/questionnaire/terms, rather than every new RFQ silently
showing up pre-filled with a 30-line reference draft the buyer never
typed. The full reference draft is still available on demand
(seed_reference_draft) for the "Seed & extract all" demo shortcut and
direct API/test use, but it never overwrites real buyer-authored content.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.copilot.reference_draft import SUPPLIERS, reference_draft_dict
from app.copilot.tools import get_current_draft
from app.models import AuditLog, ChatTurn, Rfx, RfxVersion, Supplier
from app.schemas.draft import RfxDraft

GREETING = (
    "Hi! I'll help you put this RFQ together — let's go section by section.\n\n"
    "First, **scope**: what product/category are you sourcing, which site is it "
    "for, and what are the contract start/end dates?\n\n"
    "Once that's set we'll cover the line items (species, form, grade, volumes), "
    "then the supplier questionnaire, then commercial terms."
)


def _seed_suppliers_and_history(session: Session, rfx_id: int) -> None:
    for supplier in SUPPLIERS:
        exists = session.exec(
            select(Supplier).where(Supplier.rfx_id == rfx_id, Supplier.name == supplier["name"])
        ).first()
        if not exists:
            session.add(Supplier(rfx_id=rfx_id, name=supplier["name"], email=supplier.get("email")))
    session.commit()

    # Synthetic historical PO/RFQ data — global across all suppliers, not
    # scoped to one rfx_id; idempotent, so calling it again for a second
    # RFx is a no-op once it's run once.
    import scripts.seed_history as seed_history_module

    seed_history_module.main()


def _next_version_number(session: Session, rfx_id: int) -> int:
    latest = session.exec(
        select(RfxVersion).where(RfxVersion.rfx_id == rfx_id).order_by(RfxVersion.version.desc())
    ).first()
    return (latest.version if latest else 0) + 1


def seed_new_rfx(session: Session, rfx_id: int) -> None:
    """Called when a new RFx is created: known supplier contacts + purchase
    history, but a blank draft — plus a canned greeting (not an LLM call)
    so the buyer sees the co-pilot asking questions immediately instead of
    a "No messages yet" empty state.
    """
    rfx = session.get(Rfx, rfx_id)
    if rfx is None:
        raise ValueError(f"rfx {rfx_id} not found")

    already_seeded = session.exec(select(RfxVersion).where(RfxVersion.rfx_id == rfx_id)).first()
    if already_seeded is not None:
        return

    _seed_suppliers_and_history(session, rfx_id)

    version = RfxVersion(
        rfx_id=rfx_id, version=1, draft_json=RfxDraft().model_dump(), created_by="system", cause="seed_blank"
    )
    session.add(version)
    session.add(ChatTurn(rfx_id=rfx_id, thread="copilot", role="assistant", content=GREETING))
    session.add(AuditLog(actor="system", action="blank_draft_seeded", entity=f"rfx:{rfx_id}"))
    session.commit()


def seed_reference_draft(session: Session, rfx_id: int) -> None:
    """Loads the full reference RFQ (30 lines, 12 questions, terms) — kept
    for direct API/test use and as the "Seed & extract all" demo shortcut,
    which needs an existing line list for supplier replies to match
    against. Never overwrites a draft that already has real lines in it,
    so it can't clobber something the buyer built through chat.
    """
    rfx = session.get(Rfx, rfx_id)
    if rfx is None:
        raise ValueError(f"rfx {rfx_id} not found")

    current_draft = get_current_draft(session, rfx_id)
    if current_draft.get("lines"):
        return

    _seed_suppliers_and_history(session, rfx_id)

    version = RfxVersion(
        rfx_id=rfx_id,
        version=_next_version_number(session, rfx_id),
        draft_json=reference_draft_dict(),
        created_by="system",
        cause="seed_reference",
    )
    session.add(version)
    session.add(AuditLog(actor="system", action="reference_draft_seeded", entity=f"rfx:{rfx_id}"))
    session.commit()

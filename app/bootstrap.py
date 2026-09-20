"""Auto-seeding for a freshly created RFx. Previously exposed as two manual
buttons ("Load reference RFx", "Seed sourcing history") on the Draft/Inbox
screens; now runs automatically whenever a new Rfx row is created, so the
buyer never sees an empty draft or has to know these steps exist.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.copilot.reference_draft import reference_draft_dict
from app.models import AuditLog, Rfx, RfxVersion, Supplier


def seed_new_rfx(session: Session, rfx_id: int) -> None:
    rfx = session.get(Rfx, rfx_id)
    if rfx is None:
        raise ValueError(f"rfx {rfx_id} not found")

    already_seeded = session.exec(select(RfxVersion).where(RfxVersion.rfx_id == rfx_id)).first()
    if already_seeded is not None:
        return

    draft_dict = reference_draft_dict()
    for supplier in draft_dict["suppliers"]:
        exists = session.exec(
            select(Supplier).where(Supplier.rfx_id == rfx_id, Supplier.name == supplier["name"])
        ).first()
        if not exists:
            session.add(Supplier(rfx_id=rfx_id, name=supplier["name"], email=supplier.get("email")))
    session.commit()

    version = RfxVersion(rfx_id=rfx_id, version=1, draft_json=draft_dict, created_by="system", cause="seed")
    session.add(version)
    session.add(AuditLog(actor="system", action="reference_draft_seeded", entity=f"rfx:{rfx_id}"))
    session.commit()

    # Synthetic historical PO/RFQ data (scripts/seed_history.py) — global
    # across all suppliers, not scoped to one rfx_id; idempotent, so calling
    # it again for a second RFx is a no-op once it's run once.
    import scripts.seed_history as seed_history_module

    seed_history_module.main()

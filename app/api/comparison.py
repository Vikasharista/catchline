from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import Assumption, Eligibility, ExtractedItem, NormalizedQuote, Supplier
from app.validate.service import qualified_vendors_table, suggest_vendors_from_history

router = APIRouter(prefix="/api")


@router.get("/rfx/{rfx_id}/qualified-vendors")
def qualified_vendors(rfx_id: int, session: Session = Depends(get_session)):
    return {"rows": qualified_vendors_table(session, rfx_id)}


@router.get("/rfx/{rfx_id}/vendor-shortlist")
def vendor_shortlist(rfx_id: int, session: Session = Depends(get_session)):
    """Pre-send shortlist from purchase history — see suggest_vendors_from_history."""
    return {"by_line": suggest_vendors_from_history(session, rfx_id)}


@router.get("/rfx/{rfx_id}/comparison")
def comparison_grid(rfx_id: int, session: Session = Depends(get_session)):
    suppliers = session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()
    supplier_ids = [s.id for s in suppliers]
    quotes = session.exec(select(NormalizedQuote).where(NormalizedQuote.supplier_id.in_(supplier_ids))).all()
    eligibility = {
        e.supplier_id: e for e in session.exec(select(Eligibility).where(Eligibility.supplier_id.in_(supplier_ids))).all()
    }

    rows = []
    for q in quotes:
        item = session.get(ExtractedItem, q.item_id)
        rows.append(
            {
                "line_id": q.line_id,
                "supplier_id": q.supplier_id,
                "eur_kg_net_dap": q.eur_kg_net_dap,
                "status": q.status,
                "species": (item.fields_json or {}).get("species") if item else None,
            }
        )

    headers = [
        {
            "supplier_id": s.id,
            "name": s.name,
            "eligibility": eligibility[s.id].status if s.id in eligibility else "unknown",
            "coverage": len([r for r in rows if r["supplier_id"] == s.id]),
        }
        for s in suppliers
    ]

    return {"headers": headers, "rows": rows}


class AssumptionBody(BaseModel):
    key: str
    value: dict | float | str


@router.put("/rfx/{rfx_id}/assumptions")
def set_assumption(rfx_id: int, body: AssumptionBody, session: Session = Depends(get_session)):
    existing = session.get(Assumption, body.key)
    if existing is None:
        existing = Assumption(key=body.key, value_json={"value": body.value})
    else:
        existing.value_json = {"value": body.value}
    session.add(existing)
    session.commit()
    return {"key": body.key, "value": body.value}


@router.get("/rfx/{rfx_id}/assumptions")
def get_assumptions(rfx_id: int, session: Session = Depends(get_session)):
    rows = session.exec(select(Assumption)).all()
    return {r.key: r.value_json.get("value") for r in rows}

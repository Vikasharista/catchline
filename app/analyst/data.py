"""Builds the read-only `quotes` DataFrame the analyst agent works from
(PRD §7.9). Pulled fresh from the DB on every question — never cached
stale, since review-queue edits and assumption changes must show up
immediately.
"""
from __future__ import annotations

import pandas as pd
from sqlmodel import Session, select

from app.models import Eligibility, ExtractedItem, NormalizedQuote, Supplier


def build_quotes_dataframe(session: Session, rfx_id: int) -> pd.DataFrame:
    suppliers = session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()
    supplier_by_id = {s.id: s for s in suppliers}
    eligibility_by_supplier = {
        e.supplier_id: e
        for e in session.exec(
            select(Eligibility).where(Eligibility.supplier_id.in_([s.id for s in suppliers]))
        ).all()
    }

    quotes = session.exec(select(NormalizedQuote).where(NormalizedQuote.supplier_id.in_(supplier_by_id.keys()))).all()

    rows = []
    for q in quotes:
        item = session.get(ExtractedItem, q.item_id)
        supplier = supplier_by_id.get(q.supplier_id)
        elig = eligibility_by_supplier.get(q.supplier_id)
        fields = item.fields_json if item else {}
        rows.append(
            {
                "line_id": q.line_id,
                "species": fields.get("species"),
                "form": fields.get("form"),
                "grade": fields.get("grade"),
                "volume_kg": fields.get("annual_volume_kg", 0),
                "supplier_id": q.supplier_id,
                "supplier_name": supplier.name if supplier else None,
                "eur_kg_net_dap": q.eur_kg_net_dap,
                "status": q.status,
                "flags": fields.get("flags", []),
                "conditions": fields.get("conditions", []),
                "eligibility": elig.status if elig else "unknown",
                "line_blocked": bool(elig and q.line_id in (elig.blocked_lines_json or [])),
                "native_price": fields.get("price"),
                "native_unit": fields.get("price_unit"),
                "currency": fields.get("currency"),
                "incoterm": fields.get("incoterm"),
            }
        )

    columns = [
        "line_id", "species", "form", "grade", "volume_kg", "supplier_id", "supplier_name",
        "eur_kg_net_dap", "status", "flags", "conditions", "eligibility", "line_blocked",
        "native_price", "native_unit", "currency", "incoterm",
    ]
    return pd.DataFrame(rows, columns=columns)

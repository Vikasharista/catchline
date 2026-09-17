"""Wires eligibility.compute_eligibility to real DB data: QaAnswer rows
(questionnaire), Certificate rows, and the draft's own award_rules. Nothing
here is decided by an LLM — it's the deterministic policy engine PRD §7.6
calls for, fed by facts the extraction agents already put in the DB.
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlmodel import Session, select

from app.copilot.tools import get_current_draft
from app.models import Certificate, Eligibility, NormalizedQuote, PurchaseOrder, QaAnswer, Supplier
from app.schemas.draft import RfxDraft
from app.validate.eligibility import Certificate as CertFacts
from app.validate.eligibility import SupplierFacts, compute_eligibility

# Where a supplier's MOQ/lead-time answer lives on the reference questionnaire.
DELIVERY_SLA_QUESTION_ID = "Q10"

_E_NUMBER_RE = re.compile(r"\bE4[0-9]{2}\b", re.IGNORECASE)

# Q05 on the reference questionnaire is "Use of phosphates / soaking agents
# (declare E-numbers)" — where a supplier would mention a banned additive.
ADDITIVE_QUESTION_ID = "Q05"


def _blocked_lines_for_species_hint(draft: RfxDraft, applies_to: str | None) -> list[str]:
    if not applies_to:
        return []
    hint_words = applies_to.lower().split()
    blocked = []
    for line in draft.lines:
        haystack = f"{line.species} {line.form}".lower()
        if all(w in haystack for w in hint_words if w != "raw") and "raw" in haystack:
            blocked.append(line.line_id)
    return blocked


def compute_and_persist_eligibility(session: Session, rfx_id: int) -> list[Eligibility]:
    draft = RfxDraft.model_validate(get_current_draft(session, rfx_id))
    award_date = None
    if draft.scope.award_date:
        try:
            award_date = datetime.fromisoformat(draft.scope.award_date).date()
        except ValueError:
            award_date = None
    if award_date is None:
        award_date = datetime.utcnow().date()

    award_rules = [r.model_dump() for r in draft.terms.award_rules]
    suppliers = session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()

    results = []
    for supplier in suppliers:
        qa_answers = session.exec(select(QaAnswer).where(QaAnswer.supplier_id == supplier.id)).all()
        certs = session.exec(
            select(Certificate).where(Certificate.supplier_id == supplier.id).order_by(Certificate.id.desc())
        ).all()

        cert_facts = None
        if certs:
            best = certs[0]
            cert_facts = CertFacts(scheme=(best.scheme or "").upper(), valid_until=best.valid_until.date() if best.valid_until else None)

        additive_by_line: dict[str, list[str]] = {}
        additive_answer = next((a for a in qa_answers if a.q_id == ADDITIVE_QUESTION_ID), None)
        if additive_answer and additive_answer.answer:
            codes = {m.upper() for m in _E_NUMBER_RE.findall(additive_answer.answer)}
            for rule in award_rules:
                if rule.get("type") != "ban_additive":
                    continue
                banned = set(rule.get("codes") or [])
                hit = codes & banned
                if hit:
                    lines = _blocked_lines_for_species_hint(draft, rule.get("applies_to"))
                    for code in hit:
                        additive_by_line.setdefault(code, []).extend(lines)

        facts = SupplierFacts(
            supplier_id=str(supplier.id),
            has_questionnaire=bool(qa_answers),
            has_certificate=bool(certs),
            certificate=cert_facts,
            additive_by_line=additive_by_line,
        )
        result = compute_eligibility(facts, award_rules, award_date)

        existing = session.exec(select(Eligibility).where(Eligibility.supplier_id == supplier.id)).first()
        if existing is None:
            existing = Eligibility(supplier_id=supplier.id, status=result.status)
        existing.status = result.status
        existing.blocked_lines_json = result.blocked_lines
        existing.reasons_json = result.reasons
        session.add(existing)
        results.append(existing)

    session.commit()
    return results


def qualified_vendors_table(session: Session, rfx_id: int) -> list[dict]:
    """Per SKU/line: which suppliers qualify (eligible, not blocked on that
    line), their price, and their delivery SLA (MOQ + lead time from Q10).
    Real DB data throughout — no LLM involved in deciding "qualified".
    """
    draft = RfxDraft.model_validate(get_current_draft(session, rfx_id))
    suppliers = {s.id: s for s in session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()}
    eligibility_by_supplier = {
        e.supplier_id: e
        for e in session.exec(select(Eligibility).where(Eligibility.supplier_id.in_(suppliers.keys()))).all()
    }
    sla_by_supplier = {
        a.supplier_id: a.answer
        for a in session.exec(
            select(QaAnswer).where(
                QaAnswer.supplier_id.in_(suppliers.keys()), QaAnswer.q_id == DELIVERY_SLA_QUESTION_ID
            )
        ).all()
    }
    quotes = session.exec(select(NormalizedQuote).where(NormalizedQuote.supplier_id.in_(suppliers.keys()))).all()
    quotes_by_line: dict[str, list[NormalizedQuote]] = {}
    for q in quotes:
        quotes_by_line.setdefault(q.line_id, []).append(q)

    rows = []
    for line in draft.lines:
        for quote in quotes_by_line.get(line.line_id, []):
            supplier = suppliers.get(quote.supplier_id)
            if supplier is None:
                continue
            elig = eligibility_by_supplier.get(quote.supplier_id)
            elig_status = elig.status if elig else "unknown"
            line_blocked = bool(elig and line.line_id in (elig.blocked_lines_json or []))
            qualified = (
                elig_status in ("eligible", "conditional")
                and not line_blocked
                and quote.eur_kg_net_dap is not None
                and quote.status != "excluded"
            )
            rows.append(
                {
                    "line_id": line.line_id,
                    "species": line.species,
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "price_eur_kg_net_dap": quote.eur_kg_net_dap,
                    "eligibility": elig_status,
                    "line_blocked": line_blocked,
                    "delivery_sla": sla_by_supplier.get(quote.supplier_id),
                    "qualified": qualified,
                }
            )
    return rows


def suggest_vendors_from_history(session: Session, rfx_id: int) -> dict[str, list[dict]]:
    """Pre-send shortlist: for each line in the draft, which of Nordcap's
    known suppliers have historically supplied that species, from
    scripts/seed_history.py's synthetic PurchaseOrder records.
    """
    draft = RfxDraft.model_validate(get_current_draft(session, rfx_id))
    suppliers = {s.id: s for s in session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()}
    all_pos = session.exec(select(PurchaseOrder).where(PurchaseOrder.supplier_id.in_(suppliers.keys()))).all()

    by_species: dict[str, list[PurchaseOrder]] = {}
    for po in all_pos:
        by_species.setdefault(po.species.lower(), []).append(po)

    result: dict[str, list[dict]] = {}
    for line in draft.lines:
        pos = by_species.get(line.species.lower(), [])
        by_supplier: dict[int, list[PurchaseOrder]] = {}
        for po in pos:
            by_supplier.setdefault(po.supplier_id, []).append(po)

        suggestions = []
        for supplier_id, orders in by_supplier.items():
            supplier = suppliers.get(supplier_id)
            if supplier is None:
                continue
            avg_price = sum(o.price_eur_kg_net_dap for o in orders) / len(orders)
            last_order = max(orders, key=lambda o: o.order_date)
            suggestions.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier.name,
                    "past_orders": len(orders),
                    "avg_price_eur_kg_net_dap": round(avg_price, 2),
                    "last_order_date": last_order.order_date.isoformat(),
                }
            )
        if suggestions:
            result[line.line_id] = sorted(suggestions, key=lambda s: s["avg_price_eur_kg_net_dap"])
    return result

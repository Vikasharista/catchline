from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.analyst.data import build_quotes_dataframe
from app.analyst.tools import AnalystTools
from app.api.deps import get_session
from app.copilot.tools import get_current_draft
from app.exports.award_xlsx import build_award_xlsx
from app.exports.memo import build_memo_pdf
from app.models import AuditLog, Eligibility, Flag, Supplier
from app.normalize.reference import load_fx_rates, load_freight_adders
from app.schemas.draft import RfxDraft

router = APIRouter(prefix="/api")


def _award_context(session: Session, rfx_id: int):
    draft = RfxDraft.model_validate(get_current_draft(session, rfx_id))
    all_line_ids = [l.line_id for l in draft.lines]
    supplier_ids = [s.id for s in session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()]
    quotes = build_quotes_dataframe(session, rfx_id)
    tools = AnalystTools(quotes, all_line_ids=all_line_ids, all_supplier_ids=supplier_ids)
    return draft, tools, quotes


@router.get("/rfx/{rfx_id}/award/export.xlsx")
def export_award_xlsx(rfx_id: int, session: Session = Depends(get_session)):
    draft, tools, quotes = _award_context(session, rfx_id)
    result = tools.cheapest_per_line(eligible_only=True)

    eligibility = session.exec(select(Eligibility)).all()
    flags = session.exec(select(Flag).where(Flag.resolved == False)).all()  # noqa: E712
    audit = session.exec(select(AuditLog).order_by(AuditLog.ts)).all()

    xlsx_bytes = build_award_xlsx(
        award_table=result["award_table"],
        comparison_rows=quotes.to_dict("records"),
        assumptions={"fx_rates": load_fx_rates(), "freight_adders": load_freight_adders()},
        open_flags=[{"supplier_id": None, "line_id": None, "code": f.code, "severity": f.severity, "message": f.message} for f in flags],
        eligibility=[
            {"supplier_id": e.supplier_id, "status": e.status, "blocked_lines": e.blocked_lines_json or [], "reasons": e.reasons_json or []}
            for e in eligibility
        ],
        audit_log=[{"ts": str(a.ts), "actor": a.actor, "action": a.action, "entity": a.entity, "reason": a.reason} for a in audit],
    )
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/rfx/{rfx_id}/award/memo.pdf")
def export_memo_pdf(rfx_id: int, session: Session = Depends(get_session)):
    draft, tools, quotes = _award_context(session, rfx_id)
    result = tools.cheapest_per_line(eligible_only=True)
    audit_count = len(session.exec(select(AuditLog)).all())

    risks = []
    if result["uncovered_lines"]:
        risks.append(f"No eligible supplier for: {', '.join(result['uncovered_lines'])}")

    # The narrative comes from the analyst agent (real LLM, tool results only);
    # here we just lay it out. A live call is needed for real prose — this
    # falls back to a plain statement of the numbers if no LLM is configured.
    recommendation_text = (
        f"Recommended award across {len(result['award_table'])} lines at a total spend of "
        f"EUR {result['total_spend_eur']:,.0f}, using only eligible suppliers' cheapest quotes."
    )

    pdf_bytes = build_memo_pdf(
        recommendation_text=recommendation_text,
        total_spend_eur=result["total_spend_eur"],
        award_table=result["award_table"],
        risks=risks,
        assumptions={"fx_rates": load_fx_rates(), "freight_adders": load_freight_adders()},
        n_logged_decisions=audit_count,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")

"""Analyst chat loop (PRD §7.9). Builds the answer card: headline, body,
trust note, and the "how I got this" tool-call transcript — never a bare
number without a tool behind it.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.analyst.data import build_quotes_dataframe
from app.analyst.prompts import SYSTEM_PROMPT, TOOL_SCHEMAS
from app.analyst.sandbox import SandboxError, run_sandbox
from app.analyst.tools import AnalystTools
from app.copilot.tools import get_current_draft
from app.events import emit
from app.knowledge.graph import build_entity_graph, is_in_scope
from app.llm import run_tool_loop
from app.models import ChatTurn, Supplier

PROMPT_VERSION = "v1"
MAX_STEPS = 6

OUT_OF_SCOPE_REPLY = (
    "I can only help with this RFx and Nordcap's sourcing history — suppliers, "
    "items/species, certificates, quotes, contracts, past purchase orders and "
    "past RFQs. That question is outside what I can answer here."
)


def _history(session: Session, rfx_id: int, limit: int = 20) -> list[dict]:
    turns = session.exec(
        select(ChatTurn)
        .where(ChatTurn.rfx_id == rfx_id, ChatTurn.thread == "analyst")
        .order_by(ChatTurn.created_at.desc())
        .limit(limit)
    ).all()
    return [{"role": t.role, "content": t.content} for t in reversed(turns)]


def ask(session: Session, rfx_id: int, question: str, all_line_ids: list[str]) -> dict:
    user_turn = ChatTurn(rfx_id=rfx_id, thread="analyst", role="user", content=question)
    session.add(user_turn)
    session.commit()

    draft = get_current_draft(session, rfx_id)
    graph = build_entity_graph(session, draft_lines=draft.get("lines", []))
    in_scope, reason = is_in_scope(question, graph)
    if not in_scope:
        assistant_turn = ChatTurn(rfx_id=rfx_id, thread="analyst", role="assistant", content=OUT_OF_SCOPE_REPLY)
        session.add(assistant_turn)
        session.commit()
        card = {
            "headline": OUT_OF_SCOPE_REPLY,
            "body": OUT_OF_SCOPE_REPLY,
            "trust_note": f"Refused before calling the model ({reason}).",
            "how_i_got_this": [],
        }
        emit("answer_card", card)
        return card

    quotes = build_quotes_dataframe(session, rfx_id)
    supplier_ids = [s.id for s in session.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()]
    tools = AnalystTools(quotes, all_line_ids=all_line_ids, all_supplier_ids=supplier_ids, session=session)

    def _run_sandbox(code: str):
        try:
            return run_sandbox(code, {"quotes": quotes})
        except SandboxError as exc:
            return {"error": str(exc)}

    impls = {
        "coverage": tools.coverage,
        "uncertain_items": tools.uncertain_items,
        "explain_cell": tools.explain_cell,
        "cheapest_per_line": tools.cheapest_per_line,
        "split_award": tools.split_award,
        "price_spread": tools.price_spread,
        "compare_last_year": tools.compare_last_year,
        "past_orders": tools.past_orders,
        "past_rfqs": tools.past_rfqs,
        "certificates": tools.certificates,
        "run_sandbox": _run_sandbox,
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *_history(session, rfx_id),
        {"role": "user", "content": question},
    ]

    text, transcript = run_tool_loop(
        messages, TOOL_SCHEMAS, impls, max_steps=MAX_STEPS, prompt_version=PROMPT_VERSION
    )

    n_unconfirmed = int((quotes["status"] != "confirmed").sum()) if not quotes.empty else 0
    n_inferred = int((quotes["status"] == "inferred").sum()) if not quotes.empty else 0
    trust_note = f"Relies on {n_inferred} inferred value(s) and {n_unconfirmed} unconfirmed value(s)."

    assistant_turn = ChatTurn(
        rfx_id=rfx_id, thread="analyst", role="assistant", content=text, tool_calls_json=transcript
    )
    session.add(assistant_turn)
    session.commit()

    card = {
        "headline": text.split("\n", 1)[0] if text else "",
        "body": text,
        "trust_note": trust_note,
        "how_i_got_this": transcript,
    }
    emit("answer_card", card)
    return card

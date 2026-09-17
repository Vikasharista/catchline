"""Co-pilot chat loop (PRD §7.2). A real LLM call every turn; tools are the
only way it can affect the draft (and even then, only via a pending
proposal — see apply.py)."""
from __future__ import annotations

from sqlmodel import Session

from app.copilot.prompts import SYSTEM_PROMPT, TOOL_SCHEMAS
from app.copilot.tools import CopilotTools, get_current_draft
from app.knowledge.graph import build_entity_graph, is_in_scope
from app.llm import run_tool_loop
from app.models import ChatTurn

PROMPT_VERSION = "v1"
MAX_STEPS = 6

OUT_OF_SCOPE_REPLY = (
    "I can only help with drafting and discussing this RFx — scope, line "
    "items, questionnaire, terms, suppliers, and Nordcap's sourcing history. "
    "That's outside what I can help with here."
)


def _history(session: Session, rfx_id: int, limit: int = 20) -> list[dict]:
    from sqlmodel import select

    turns = session.exec(
        select(ChatTurn)
        .where(ChatTurn.rfx_id == rfx_id, ChatTurn.thread == "copilot")
        .order_by(ChatTurn.created_at.desc())
        .limit(limit)
    ).all()
    return [{"role": t.role, "content": t.content} for t in reversed(turns)]


def chat(session: Session, rfx_id: int, buyer_message: str) -> dict:
    user_turn = ChatTurn(rfx_id=rfx_id, thread="copilot", role="user", content=buyer_message)
    session.add(user_turn)
    session.commit()
    session.refresh(user_turn)

    draft = get_current_draft(session, rfx_id)
    graph = build_entity_graph(session, draft_lines=draft.get("lines", []))
    in_scope, reason = is_in_scope(buyer_message, graph)
    if not in_scope:
        session.add(
            ChatTurn(rfx_id=rfx_id, thread="copilot", role="assistant", content=OUT_OF_SCOPE_REPLY)
        )
        session.commit()
        return {"text": OUT_OF_SCOPE_REPLY, "proposals": [], "questions": [], "refused_reason": reason}

    tools = CopilotTools(session, rfx_id, chat_turn_id=user_turn.id)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *_history(session, rfx_id),
        {"role": "user", "content": buyer_message},
    ]

    text, transcript = run_tool_loop(
        messages,
        TOOL_SCHEMAS,
        tools.as_impls(),
        max_steps=MAX_STEPS,
        prompt_version=PROMPT_VERSION,
    )

    assistant_turn = ChatTurn(
        rfx_id=rfx_id,
        thread="copilot",
        role="assistant",
        content=text,
        tool_calls_json=transcript,
    )
    session.add(assistant_turn)
    session.commit()

    return {
        "text": text,
        "proposals": [p.id for p in tools.created_proposals],
        "questions": [q.id for q in tools.created_questions],
    }

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.api.admin import router as admin_router
from app.api.analyst import router as analyst_router
from app.api.award import router as award_router
from app.api.comparison import router as comparison_router
from app.api.inbox import router as inbox_router
from app.api.review import router as review_router
from app.api.rfx import router as rfx_router
from app.copilot.tools import get_current_draft, get_pending_proposals, get_section_states
from app.db import engine, init_db
from app.events import subscribe, unsubscribe
from app.models import Rfx, Supplier

app = FastAPI(title="Catchline")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

for router in (rfx_router, inbox_router, review_router, comparison_router, analyst_router, award_router, admin_router):
    app.include_router(router)

NAV_STEPS = [
    {"key": "draft", "label": "RFQ", "href": "/rfx/{id}/draft"},
    {"key": "inbox", "label": "Inbox", "href": "/rfx/{id}/inbox"},
    {"key": "review", "label": "Review", "href": "/rfx/{id}/review"},
    {"key": "compare", "label": "Compare", "href": "/rfx/{id}/compare"},
    {"key": "ask", "label": "Ask", "href": "/rfx/{id}/ask"},
    {"key": "award", "label": "Award", "href": "/rfx/{id}/award"},
]

SCREEN_TITLES = {
    "draft": "Build the RFQ with the co-pilot",
    "inbox": "Supplier replies",
    "review": "Review queue",
    "compare": "Comparison grid",
    "ask": "Ask the analyst",
    "award": "Award and export",
}


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def _nav_context(rfx: Rfx | None, active: str):
    steps = []
    for i, s in enumerate(NAV_STEPS):
        steps.append(
            {
                "key": s["key"],
                "label": s["label"],
                "href": s["href"].format(id=rfx.id if rfx else 0),
                "done": rfx is not None and _step_index(active) > i,
                "locked": rfx is None,
            }
        )
    return steps


def _step_index(key: str) -> int:
    for i, s in enumerate(NAV_STEPS):
        if s["key"] == key:
            return i
    return 0


@app.get("/")
def root(request: Request):
    with Session(engine) as s:
        rows = s.exec(select(Rfx).order_by(Rfx.id.desc())).all()
        rfqs = []
        for rfx in rows:
            draft = get_current_draft(s, rfx.id)
            rfqs.append(
                {
                    "id": rfx.id,
                    "status": rfx.status,
                    "title": (draft.get("scope") or {}).get("title") or f"RFX-{rfx.id}",
                    "line_count": len(draft.get("lines", [])),
                    "supplier_count": len(s.exec(select(Supplier).where(Supplier.rfx_id == rfx.id)).all()),
                    "created_at": rfx.created_at,
                }
            )

    return templates.TemplateResponse(
        "rfq_list.html",
        {
            "request": request,
            "title": "RFQs",
            "heading": "RFQs",
            "active_step": None,
            "crumb": "All RFQs",
            "nav_steps": [],
            "rfx": None,
            "agents_working": 0,
            "rfqs": rfqs,
        },
    )


@app.get("/rfx/{rfx_id}/{screen}")
def screen_view(request: Request, rfx_id: int, screen: str):
    with Session(engine) as s:
        rfx = s.get(Rfx, rfx_id)
        supplier_count = len(s.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()) if rfx else 0
        draft = get_current_draft(s, rfx_id) if rfx else {}
        sections = get_section_states(s, rfx_id) if rfx else {}
        pending_count = len(get_pending_proposals(s, rfx_id)) if rfx else 0

    heading = SCREEN_TITLES.get(screen, "Not found")
    rfx_ctx = None
    if rfx:
        rfx_ctx = {
            "id": rfx.id,
            "rfx_number": (draft.get("scope") or {}).get("title") or f"RFX-{rfx.id}",
            "line_count": len(draft.get("lines", [])),
            "supplier_count": supplier_count,
        }

    template_name = f"screens/{screen}.html"
    try:
        templates.get_template(template_name)
    except Exception:
        template_name = "screen.html"

    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "title": heading,
            "heading": heading,
            "body": "",
            "active_step": screen,
            "crumb": heading,
            "nav_steps": _nav_context(rfx, screen),
            "rfx": rfx_ctx,
            "agents_working": 0,
            "rfx_id": rfx_id,
            "draft": draft,
            "sections": sections,
            "pending_count": pending_count,
        },
    )


@app.get("/api/events")
async def events():
    queue = subscribe()

    async def event_stream():
        try:
            while True:
                payload = await queue.get()
                yield payload
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/health")
def health():
    return {"status": "ok"}

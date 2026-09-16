from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from app.db import get_session, init_db
from app.models import Rfx, Supplier

app = FastAPI(title="Catchline")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

NAV_STEPS = [
    {"key": "draft", "label": "Draft", "href": "/rfx/{id}/draft"},
    {"key": "inbox", "label": "Inbox", "href": "/rfx/{id}/inbox"},
    {"key": "review", "label": "Review", "href": "/rfx/{id}/review"},
    {"key": "compare", "label": "Compare", "href": "/rfx/{id}/compare"},
    {"key": "ask", "label": "Ask", "href": "/rfx/{id}/ask"},
    {"key": "award", "label": "Award", "href": "/rfx/{id}/award"},
]

SCREEN_COPY = {
    "draft": ("Draft the RFx with the co-pilot", "Chat drafts scope, lines, questionnaire and terms. Nothing reaches the draft until you accept it."),
    "inbox": ("Supplier replies", "Simulate or upload supplier replies; extraction runs per document."),
    "review": ("Review queue", "Flagged and uncertain items, one at a time."),
    "compare": ("Comparison grid", "Lines × suppliers in EUR/kg net DAP Boulogne."),
    "ask": ("Ask the analyst", "Plain-English questions, answered from tools only."),
    "award": ("Award and export", "Memo and Excel export, built from tool results."),
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
def root():
    return RedirectResponse(url="/rfx/latest/draft")


@app.get("/rfx/latest/{screen}")
def latest_redirect(screen: str):
    from app.db import engine
    from sqlmodel import Session

    with Session(engine) as s:
        rfx = s.exec(select(Rfx).order_by(Rfx.id.desc())).first()
        if rfx is None:
            rfx = Rfx()
            s.add(rfx)
            s.commit()
            s.refresh(rfx)
    return RedirectResponse(url=f"/rfx/{rfx.id}/{screen}")


@app.get("/rfx/{rfx_id}/{screen}")
def screen_view(request: Request, rfx_id: int, screen: str):
    from app.db import engine
    from sqlmodel import Session

    with Session(engine) as s:
        rfx = s.get(Rfx, rfx_id)
        supplier_count = len(s.exec(select(Supplier).where(Supplier.rfx_id == rfx_id)).all()) if rfx else 0

    heading, body = SCREEN_COPY.get(screen, ("Not found", ""))
    rfx_ctx = None
    if rfx:
        rfx_ctx = {
            "id": rfx.id,
            "rfx_number": "RFQ-2026-FROZ-017",
            "line_count": 30,
            "supplier_count": supplier_count,
        }

    return templates.TemplateResponse(
        "screen.html",
        {
            "request": request,
            "title": heading,
            "heading": heading,
            "body": body,
            "active_step": screen,
            "crumb": heading,
            "nav_steps": _nav_context(rfx, screen),
            "rfx": rfx_ctx,
            "agents_working": 0,
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}

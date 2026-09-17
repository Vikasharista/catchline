from __future__ import annotations

import subprocess
import sys

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import AuditLog

router = APIRouter(prefix="/api")


@router.get("/audit")
def audit_log(session: Session = Depends(get_session)):
    rows = session.exec(select(AuditLog).order_by(AuditLog.ts.desc())).all()
    return [
        {"ts": r.ts, "actor": r.actor, "action": r.action, "entity": r.entity, "reason": r.reason} for r in rows
    ]


@router.post("/admin/reset")
def reset_demo():
    subprocess.run([sys.executable, "scripts/reset_demo.py"], check=True)
    return {"status": "reset"}

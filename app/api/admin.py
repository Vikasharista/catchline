from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_session
from app.config import settings
from app.models import AuditLog

router = APIRouter(prefix="/api")


def _mask(key: str | None) -> dict:
    if not key:
        return {"set": False, "length": 0, "preview": None}
    key = key.strip()
    preview = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
    return {"set": True, "length": len(key), "preview": preview}

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_script(relative_path: str) -> None:
    # subprocess.run doesn't set sys.path[0] to the repo root the way running
    # the script directly from there does, so `from app... import ...` inside
    # the script fails with ModuleNotFoundError unless PYTHONPATH is passed
    # explicitly (bit us once already with scripts/score_extraction.py).
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(
        [sys.executable, relative_path],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(
            502,
            detail={"error": f"{relative_path} failed", "stderr": result.stderr[-2000:]},
        )


@router.get("/audit")
def audit_log(session: Session = Depends(get_session)):
    rows = session.exec(select(AuditLog).order_by(AuditLog.ts.desc())).all()
    return [
        {"ts": r.ts, "actor": r.actor, "action": r.action, "entity": r.entity, "reason": r.reason} for r in rows
    ]


@router.post("/admin/reset")
def reset_demo():
    _run_script("scripts/reset_demo.py")
    return {"status": "reset"}


@router.post("/admin/seed-history")
def seed_history():
    """Seeds synthetic past-PO/past-RFQ demo data — see scripts/seed_history.py."""
    _run_script("scripts/seed_history.py")
    return {"status": "seeded"}


@router.get("/admin/llm-status")
def llm_status():
    """Diagnoses "Missing credentials" / wrong-model errors without ever
    exposing a real key: what model config this exact running process
    resolved (LLM_MODEL/LLM_FALLBACK), and whether each provider key is
    present in its environment, its length, and a masked preview — enough
    to catch "the var is set on the wrong Render service", "it's empty",
    or "it got truncated when pasted" without guessing blind.
    """
    return {
        "llm_model": settings.llm_model,
        "llm_fallback": settings.llm_fallback,
        "keys": {
            "OPENAI_API_KEY": _mask(settings.openai_api_key),
            "ANTHROPIC_API_KEY": _mask(settings.anthropic_api_key),
            "GEMINI_API_KEY": _mask(settings.gemini_api_key),
            "GROQ_API_KEY": _mask(settings.groq_api_key),
        },
    }

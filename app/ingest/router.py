"""Turns any supported supplier-reply file into an IngestedDoc of chunks.

This module only extracts raw content and locators (PRD §7.4 table). It never
interprets or converts anything — that's the extract/ and normalize/ agents'
job. Keeping this dumb is what lets the extraction eval attribute every
number to an exact source location.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_EXTENSIONS = {".xlsx", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".eml"}


@dataclass
class Chunk:
    kind: str  # text | table | image
    content: Any
    locator: str


@dataclass
class IngestedDoc:
    filename: str
    kind: str
    chunks: list[Chunk] = field(default_factory=list)


def route(path: Path) -> IngestedDoc:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    if ext == ".xlsx":
        from app.ingest.xlsx import ingest

        return ingest(path)
    if ext == ".pdf":
        from app.ingest.pdf import ingest

        return ingest(path)
    if ext == ".docx":
        from app.ingest.docx import ingest

        return ingest(path)
    if ext in (".jpg", ".jpeg", ".png"):
        from app.ingest.image import ingest

        return ingest(path)
    if ext == ".eml":
        from app.ingest.eml import ingest

        return ingest(path)

    raise AssertionError("unreachable")

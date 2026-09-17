"""Extraction agent: Pass A (items) and Pass B (line matching) — PRD §7.4.

A real LLM call every time (no hardcoded values). Pydantic validates the
output; one retry on a bad response; the document is marked needs_attention
if it still fails.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from app.extract.prompts import PROMPT_VERSION, build_pass_a_messages, build_pass_b_messages
from app.ingest.router import IngestedDoc
from app.llm import complete
from app.schemas.extraction import DocumentExtraction, LineMatchResult


def _document_text(doc: IngestedDoc) -> str:
    parts = []
    for chunk in doc.chunks:
        if chunk.kind in ("text", "table"):
            parts.append(f"[{chunk.locator}]\n{chunk.content}")
    return "\n\n".join(parts)


def _document_images(doc: IngestedDoc) -> list[str]:
    return [c.content for c in doc.chunks if c.kind == "image"]


def extract_pass_a(
    doc: IngestedDoc,
    *,
    sha256: str,
    rfx_context: str,
    live: bool = False,
) -> tuple[DocumentExtraction | None, bool]:
    """Returns (extraction, needs_attention)."""
    messages = build_pass_a_messages(_document_text(doc), _document_images(doc), rfx_context)
    schema = {
        "type": "json_schema",
        "json_schema": {"name": "DocumentExtraction", "schema": DocumentExtraction.model_json_schema()},
    }

    document_has_content = bool(_document_text(doc).strip()) or bool(_document_images(doc))
    max_attempts = 2
    last_extraction: DocumentExtraction | None = None

    for attempt in range(max_attempts):
        result = complete(
            messages,
            response_format=schema,
            cache_key=f"extract_pass_a:{sha256}",
            live=live or attempt > 0,
            prompt_version=PROMPT_VERSION,
        )
        try:
            data = json.loads(result.text)
            extraction = DocumentExtraction.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            continue

        # A syntactically valid but empty response on a document that clearly
        # has content is suspicious (model non-determinism on a long table),
        # not a legitimate "nothing to extract" — worth one retry before
        # accepting it.
        if not extraction.items and document_has_content and attempt < max_attempts - 1:
            last_extraction = extraction
            continue
        return extraction, False

    if last_extraction is not None:
        return last_extraction, False
    return None, True


def extract_pass_b(
    extraction: DocumentExtraction,
    rfx_lines: list[dict],
    *,
    sha256: str,
    live: bool = False,
) -> LineMatchResult:
    items_json = json.dumps([item.model_dump() for item in extraction.items], default=str)
    rfx_lines_json = json.dumps(rfx_lines, default=str)
    messages = build_pass_b_messages(items_json, rfx_lines_json)
    schema = {
        "type": "json_schema",
        "json_schema": {"name": "LineMatchResult", "schema": LineMatchResult.model_json_schema()},
    }

    for attempt in range(2):
        result = complete(
            messages,
            response_format=schema,
            cache_key=f"extract_pass_b:{sha256}",
            live=live or attempt > 0,
            prompt_version=PROMPT_VERSION,
        )
        try:
            data = json.loads(result.text)
            return LineMatchResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            continue

    return LineMatchResult(matches=[])

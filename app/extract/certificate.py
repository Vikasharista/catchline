"""Extracts scheme/grade/validity from a supplier's food-safety certificate.
A real LLM call, same as the quote extraction — reads the document exactly
as printed, never guesses a validity date.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from app.extract.agent import _document_images, _document_text
from app.ingest.router import IngestedDoc
from app.llm import complete
from app.schemas.certificate import CertificateExtraction

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You extract the certification scheme, grade, certificate
number and expiry date from a supplier's food-safety certificate.

Rules:
- Read the scheme name, grade and dates exactly as printed. Never guess an
  expiry date that isn't visible.
- If the document is illegible or doesn't look like a certificate, set
  legible to false and leave the other fields null.
- valid_until must be an ISO date (YYYY-MM-DD) if a date is given.
- Output must match the given JSON schema exactly. No commentary outside the JSON.
"""


def extract_certificate(
    doc: IngestedDoc, *, sha256: str, live: bool = False
) -> CertificateExtraction | None:
    content: list[dict] = [{"type": "text", "text": _document_text(doc) or "(no extracted text — see attached image)"}]
    for b64 in _document_images(doc):
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    schema = {
        "type": "json_schema",
        "json_schema": {"name": "CertificateExtraction", "schema": CertificateExtraction.model_json_schema()},
    }

    for attempt in range(2):
        result = complete(
            messages,
            response_format=schema,
            cache_key=f"extract_certificate:{sha256}",
            live=live or attempt > 0,
            prompt_version=PROMPT_VERSION,
        )
        try:
            return CertificateExtraction.model_validate(json.loads(result.text))
        except (json.JSONDecodeError, ValidationError):
            continue

    return None

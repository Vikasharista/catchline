"""LLM auditor (PRD §7.6): one real LLM call per supplier, given its
questionnaire answers, certificate extraction and document notes, looking
for contradictions between what a supplier claims and what its documents
show. Cut-able per PRD §13 — keep the rule-based certificate-expiry check
(eligibility.py) even if this is cut.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from app.llm import complete

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You audit a seafood supplier's RFx reply for contradictions
between their questionnaire answers, their certificate, and their other
documents. Only report a contradiction if you can point to evidence from
both sides. Do not speculate. If nothing contradicts, return an empty list.
Output must match the given JSON schema exactly. No commentary outside the JSON.
"""


class Contradiction(BaseModel):
    summary: str
    evidence_a: str
    evidence_b: str


class AuditResult(BaseModel):
    contradictions: list[Contradiction] = Field(default_factory=list)


def audit_supplier(
    supplier_name: str,
    questionnaire_answers: list[dict],
    certificate_text: str | None,
    document_notes: str,
    *,
    cache_key: str,
    live: bool = False,
) -> AuditResult:
    user_content = (
        f"Supplier: {supplier_name}\n\n"
        f"Questionnaire answers:\n{json.dumps(questionnaire_answers, default=str)}\n\n"
        f"Certificate (as extracted):\n{certificate_text or 'none received'}\n\n"
        f"Other document notes:\n{document_notes}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    schema = {
        "type": "json_schema",
        "json_schema": {"name": "AuditResult", "schema": AuditResult.model_json_schema()},
    }

    for attempt in range(2):
        result = complete(
            messages,
            response_format=schema,
            cache_key=f"audit:{cache_key}",
            live=live or attempt > 0,
            prompt_version=PROMPT_VERSION,
        )
        try:
            return AuditResult.model_validate(json.loads(result.text))
        except (json.JSONDecodeError, ValidationError):
            continue

    return AuditResult(contradictions=[])

"""Section sign-off checks (PRD §7.2 table). Pure functions: draft in,
list of failure strings out. Empty list means the section can be signed off.
"""
from __future__ import annotations

from datetime import date, datetime

from app.schemas.draft import RfxDraft

GLAZED_SPECIES = {"vannamei shrimp (farmed)", "black tiger shrimp (farmed)", "loligo squid (wild)"}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def check_scope(draft: RfxDraft) -> list[str]:
    s = draft.scope
    failures = []
    if not s.incoterm:
        failures.append("Incoterm is not set")
    if not s.incoterm_place:
        failures.append("Incoterm place is not set")
    if not s.currency:
        failures.append("Currency is not set")
    if not s.weight_basis:
        failures.append("Weight basis (net/gross) is not set")
    if not s.contract_start or not s.contract_end:
        failures.append("Contract dates are not set")
    if not s.response_deadline:
        failures.append("Response deadline is not set")
    if not s.award_date:
        failures.append("Award date is not set")

    deadline = _parse_date(s.response_deadline)
    award = _parse_date(s.award_date)
    if deadline and award and not (deadline < award):
        failures.append("Response deadline must be before the award date")

    return failures


def check_lines(draft: RfxDraft) -> list[str]:
    failures = []
    if not draft.lines:
        failures.append("At least one line item is required")
        return failures

    ids = [line.line_id for line in draft.lines]
    if len(ids) != len(set(ids)):
        failures.append("Line IDs must be unique")

    for line in draft.lines:
        if not (line.species and line.form and line.grade and line.unit):
            failures.append(f"{line.line_id}: species, form, grade and unit are all required")
        if not line.annual_volume_kg or line.annual_volume_kg <= 0:
            failures.append(f"{line.line_id}: annual volume must be greater than 0")

    return failures


def check_questionnaire(draft: RfxDraft) -> list[str]:
    failures = []
    if not draft.questionnaire:
        failures.append("At least one question is required")
        return failures

    valid_refs = {"award_date", "response_deadline", "contract_start", "contract_end"}
    for q in draft.questionnaire:
        if q.pass_rule and q.pass_rule.ref and q.pass_rule.ref not in valid_refs:
            failures.append(f"{q.q_id}: pass_rule references an unknown field '{q.pass_rule.ref}'")

    return failures


def check_terms(draft: RfxDraft) -> list[str]:
    failures = []
    w = draft.terms.eval_weights
    total = w.price + w.quality + w.commercial
    if round(total) != 100:
        failures.append(f"Evaluation weights add up to {round(total)}%, not 100%")

    has_glazed_line = any(line.species.lower() in GLAZED_SPECIES for line in draft.lines)
    if has_glazed_line and draft.terms.glaze_cap_pct is None:
        failures.append("A glazed species is on the draft but no glaze cap is set")

    if not draft.terms.payment_terms:
        failures.append("Payment terms are not set")

    return failures


def check_custom_section(draft: RfxDraft, key: str) -> list[str]:
    section = next((s for s in draft.custom_sections if s.key == key), None)
    if section is None:
        return [f"Section '{key}' not found"]
    failures = []
    if not section.title.strip():
        failures.append("Title is empty")
    if not section.body_md.strip():
        failures.append("Body is empty")
    return failures


SECTION_CHECKS = {
    "scope": check_scope,
    "lines": check_lines,
    "questionnaire": check_questionnaire,
    "terms": check_terms,
}


def run_check(draft: RfxDraft, section_key: str) -> list[str]:
    if section_key in SECTION_CHECKS:
        return SECTION_CHECKS[section_key](draft)
    if section_key.startswith("custom:"):
        return check_custom_section(draft, section_key.removeprefix("custom:"))
    return [f"Unknown section '{section_key}'"]

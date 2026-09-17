"""Deterministic eligibility engine (PRD §7.6). Applies the RFx's own
award_rules to structured facts about a supplier — never an LLM judgment call.
The facts themselves (certificate data, which lines use a banned additive)
come from extraction/questionnaire parsing upstream; this module only
applies the buyer's policy to those facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Certificate:
    scheme: str
    valid_until: date | None


@dataclass
class SupplierFacts:
    supplier_id: str
    has_questionnaire: bool
    has_certificate: bool
    certificate: Certificate | None = None
    # additive code -> line_ids where that additive is declared used
    additive_by_line: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class EligibilityResult:
    status: str  # eligible | not_eligible | conditional | unknown
    blocked_lines: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def compute_eligibility(
    facts: SupplierFacts,
    award_rules: list[dict],
    award_date: date,
) -> EligibilityResult:
    reasons: list[str] = []
    blocked_lines: set[str] = set()
    status = "eligible"

    if not facts.has_questionnaire and not facts.has_certificate:
        return EligibilityResult(
            status="unknown",
            reasons=["No questionnaire or certificate received — quality gate not cleared, not failed"],
        )

    for rule in award_rules:
        if rule.get("type") == "require_valid_cert":
            schemes = rule.get("schemes", [])
            cert = facts.certificate
            # certificates print full scheme names ("BRCGS Food Safety Issue 9",
            # "IFS Food Higher Level") — match on the required scheme being a
            # substring, not exact equality.
            cert_matches = cert is not None and any(s.upper() in cert.scheme.upper() for s in schemes)
            if not cert_matches:
                status = "not_eligible"
                reasons.append(f"No valid certificate for required scheme(s): {', '.join(schemes)}")
            elif cert.valid_until is not None and cert.valid_until < award_date:
                status = "not_eligible"
                reasons.append(
                    f"{cert.scheme} certificate expired {cert.valid_until.isoformat()}, "
                    f"before award date {award_date.isoformat()}"
                )

        elif rule.get("type") == "ban_additive":
            banned = set(rule.get("codes", []))
            for code, lines in facts.additive_by_line.items():
                if code in banned:
                    blocked_lines.update(lines)
                    reasons.append(f"{code} declared on {', '.join(sorted(lines))} — banned by policy")

    if status == "not_eligible":
        return EligibilityResult(status="not_eligible", blocked_lines=[], reasons=reasons)

    if blocked_lines:
        return EligibilityResult(status="conditional", blocked_lines=sorted(blocked_lines), reasons=reasons)

    return EligibilityResult(status="eligible", reasons=reasons)

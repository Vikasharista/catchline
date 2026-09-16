"""RfxDraft schema (PRD §7.2). Stored as JSON with a version number in
RfxVersion.draft_json. This is the only shape the co-pilot's proposals are
validated against before they're allowed to touch a draft.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Scope(BaseModel):
    title: str | None = None
    category: str | None = None
    buyer_site: str | None = None
    contract_start: str | None = None
    contract_end: str | None = None
    incoterm: str | None = None
    incoterm_place: str | None = None
    currency: str | None = None
    weight_basis: str | None = None  # net | gross
    response_deadline: str | None = None
    award_date: str | None = None


class Line(BaseModel):
    line_id: str
    species: str
    form: str
    grade: str
    spec_notes: str | None = None
    unit: str = "kg"
    annual_volume_kg: float
    custom_fields: dict = Field(default_factory=dict)


class PassRule(BaseModel):
    type: str
    ref: str | None = None


class Question(BaseModel):
    q_id: str
    group: str  # certifications | quality | traceability | commercial
    text: str
    answer_type: str  # yes_no | text | date | file
    pass_rule: PassRule | None = None


class AwardRule(BaseModel):
    type: str
    value: float | None = None
    schemes: list[str] | None = None
    codes: list[str] | None = None
    applies_to: str | None = None


class EvalWeights(BaseModel):
    price: float = 0
    quality: float = 0
    commercial: float = 0


class Terms(BaseModel):
    payment_terms: str | None = None
    glaze_cap_pct: float | None = None
    quote_validity_days: int | None = None
    partial_quotes_allowed: bool = True
    eval_weights: EvalWeights = Field(default_factory=EvalWeights)
    award_rules: list[AwardRule] = Field(default_factory=list)


class CustomSection(BaseModel):
    key: str
    title: str
    body_md: str = ""
    requires_supplier_response: bool = False


class SupplierRef(BaseModel):
    name: str
    email: str | None = None


class RfxDraft(BaseModel):
    version: int = 0
    scope: Scope = Field(default_factory=Scope)
    lines: list[Line] = Field(default_factory=list)
    questionnaire: list[Question] = Field(default_factory=list)
    terms: Terms = Field(default_factory=Terms)
    custom_sections: list[CustomSection] = Field(default_factory=list)
    suppliers: list[SupplierRef] = Field(default_factory=list)


# Targets that make a proposal money_or_eligibility risk, per PRD §7.2 step 5.
# Checked by prefix so "lines[3].annual_volume_kg" and "lines[*].annual_volume_kg"
# both match.
MONEY_OR_ELIGIBILITY_TARGETS = (
    "annual_volume_kg",
    "scope.weight_basis",
    "scope.incoterm",
    "scope.currency",
    "terms.glaze_cap_pct",
    "terms.eval_weights",
    "terms.award_rules",
    "pass_rule",
)


def classify_risk(section_key: str, target: str, op: str) -> str:
    """Risk is decided by code, never the model (CLAUDE.md hard rule)."""
    if op in ("add", "remove") and section_key == "lines":
        return "money_or_eligibility"
    for pattern in MONEY_OR_ELIGIBILITY_TARGETS:
        if pattern in target:
            return "money_or_eligibility"
    return "normal"

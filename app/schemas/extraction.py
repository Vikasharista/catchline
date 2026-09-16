"""Pydantic models for the extraction agent's structured output (PRD §7.4)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Condition(BaseModel):
    scope: str
    condition: str


class QuestionnaireAnswer(BaseModel):
    q_id: str
    answer: str
    raw_text: str
    locator: str


class ExtractedItem(BaseModel):
    raw_text: str
    locator: str
    product_desc: str
    price: float | None = None
    currency: str | None = None
    price_unit: str | None = None  # per_kg | per_lb | per_block | per_carton | per_master_carton
    pack_size_kg: float | None = None
    weight_basis: str = "unknown"  # net | gross | unknown
    glaze_pct: float | None = None
    incoterm: str | None = None
    incoterm_place: str | None = None
    conditions: list[Condition] = Field(default_factory=list)
    references_prior: bool = False
    legibility: str = "clear"  # clear | partial | illegible
    confidence: float = 1.0


class DocumentExtraction(BaseModel):
    supplier_name: str | None = None
    currency: str | None = None
    incoterm: str | None = None
    incoterm_place: str | None = None
    validity: str | None = None
    payment_terms: str | None = None
    glaze_statement: str | None = None
    items: list[ExtractedItem] = Field(default_factory=list)
    questionnaire_answers: list[QuestionnaireAnswer] = Field(default_factory=list)


class LineMatch(BaseModel):
    item_index: int  # index into DocumentExtraction.items
    line_id: str | None  # None if unmatched
    match_reason: str
    match_confidence: float


class LineMatchResult(BaseModel):
    matches: list[LineMatch] = Field(default_factory=list)

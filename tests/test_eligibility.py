"""PRD §7.6 acceptance: S1 eligible, S2 conditional (blocked L17-19,L22-24),
S3 eligible, S4 not eligible (expired cert), S5 unknown.

Facts below are structured summaries of what data/seed's supplier replies and
certificates actually say (award_rules.md, ground_truth_supplier_qualification.csv
— used here for test assertions only, never as LLM input), standing in for
what the extraction pipeline will eventually produce. This tests the
deterministic policy engine, not extraction.
"""
from datetime import date

from app.validate.eligibility import Certificate, SupplierFacts, compute_eligibility

AWARD_DATE = date(2026, 9, 30)
AWARD_RULES = [
    {"type": "require_valid_cert", "schemes": ["BRCGS", "IFS"]},
    {"type": "ban_additive", "codes": ["E450", "E451", "E452"], "applies_to": "raw shrimp"},
]


def test_s1_fjordline_eligible():
    facts = SupplierFacts(
        supplier_id="S1",
        has_questionnaire=True,
        has_certificate=True,
        certificate=Certificate(scheme="BRCGS", valid_until=date(2027, 3, 31)),
    )
    result = compute_eligibility(facts, AWARD_RULES, AWARD_DATE)
    assert result.status == "eligible"


def test_s2_pacific_rim_conditional_on_raw_shrimp():
    facts = SupplierFacts(
        supplier_id="S2",
        has_questionnaire=True,
        has_certificate=True,
        certificate=Certificate(scheme="BRCGS", valid_until=date(2027, 1, 20)),
        additive_by_line={"E451": ["L17", "L18", "L19", "L22", "L23", "L24"]},
    )
    result = compute_eligibility(facts, AWARD_RULES, AWARD_DATE)
    assert result.status == "conditional"
    assert result.blocked_lines == ["L17", "L18", "L19", "L22", "L23", "L24"]


def test_s3_atlantico_eligible():
    facts = SupplierFacts(
        supplier_id="S3",
        has_questionnaire=True,
        has_certificate=True,
        certificate=Certificate(scheme="IFS", valid_until=date(2027, 6, 30)),
    )
    result = compute_eligibility(facts, AWARD_RULES, AWARD_DATE)
    assert result.status == "eligible"


def test_s4_oceanis_not_eligible_expired_cert():
    facts = SupplierFacts(
        supplier_id="S4",
        has_questionnaire=True,
        has_certificate=True,
        certificate=Certificate(scheme="BRCGS", valid_until=date(2026, 8, 31)),
    )
    result = compute_eligibility(facts, AWARD_RULES, AWARD_DATE)
    assert result.status == "not_eligible"


def test_s5_baltic_blue_unknown_no_questionnaire():
    facts = SupplierFacts(supplier_id="S5", has_questionnaire=False, has_certificate=False)
    result = compute_eligibility(facts, AWARD_RULES, AWARD_DATE)
    assert result.status == "unknown"

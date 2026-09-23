"""Regression tests for the co-pilot's grounding dictionary: added after the
co-pilot was caught live ignoring a genuine question ("what's a reasonable
glaze cap for frozen salmon?") and reciting its intake script instead, and
separately refusing to propose anything from a message that already had
real facts in it ("salmon and cod, ~100 tonnes, delivered Boulogne")
because it always waited for a whole section before acting. The fix gives
the co-pilot real reference facts to answer with (rather than improvising
numbers) plus explicit permission to answer questions and act on partial
info. These tests guard the reference data itself: real, sourced from
data/seed/.../award_rules.md and reference_draft.py's own structured
award_rules, never fabricated.
"""
from app.copilot.prompts import SYSTEM_PROMPT
from app.knowledge.glossary import NORDCAP_PRECEDENT, TERM_DEFINITIONS, glossary_context


def test_term_definitions_cover_core_seafood_and_incoterm_vocabulary():
    for term in ("DAP", "FCA", "glaze cap", "weight basis", "MOQ", "BRCGS", "IQF"):
        assert term in TERM_DEFINITIONS
        assert TERM_DEFINITIONS[term]  # non-empty


def test_nordcap_precedent_matches_real_award_rules_values():
    # These must match the real, already-used values in
    # app/copilot/reference_draft.py's structured award_rules/terms —
    # not new invented figures.
    assert "10%" in NORDCAP_PRECEDENT["glaze_cap_pct"]
    assert "30 days" in NORDCAP_PRECEDENT["payment_terms"]
    assert "60% price" in NORDCAP_PRECEDENT["eval_weights"] or "60%" in NORDCAP_PRECEDENT["eval_weights"]
    assert "BRCGS" in NORDCAP_PRECEDENT["certificates"] and "IFS" in NORDCAP_PRECEDENT["certificates"]
    assert "60%" in NORDCAP_PRECEDENT["max_supplier_share"]


def test_glossary_context_labels_precedent_as_precedent_not_a_rule():
    context = glossary_context()
    assert "precedent" in context.lower()
    assert "never write into the new draft unless the buyer confirms" in context.lower() or "buyer confirms" in context.lower()


def test_system_prompt_includes_glossary_and_intent_handling_instructions():
    assert "TERM DEFINITIONS" in SYSTEM_PROMPT
    assert "NORDCAP PRECEDENT" in SYSTEM_PROMPT
    assert "answer it directly" in SYSTEM_PROMPT
    assert "immediately" in SYSTEM_PROMPT  # act on partial info without waiting for a whole section

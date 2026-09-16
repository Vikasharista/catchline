from app.copilot.checks import check_lines, check_questionnaire, check_scope, check_terms
from app.schemas.draft import EvalWeights, Line, Question, RfxDraft, Scope, Terms


def test_scope_check_reports_missing_fields():
    failures = check_scope(RfxDraft())
    assert any("Incoterm" in f for f in failures)


def test_scope_check_deadline_before_award():
    scope = Scope(
        incoterm="DAP",
        incoterm_place="Boulogne",
        currency="EUR",
        weight_basis="net",
        contract_start="2026-10-01",
        contract_end="2027-09-30",
        response_deadline="2026-10-01",
        award_date="2026-09-30",
    )
    failures = check_scope(RfxDraft(scope=scope))
    assert any("before the award date" in f for f in failures)


def test_lines_check_requires_at_least_one():
    assert check_lines(RfxDraft()) == ["At least one line item is required"]


def test_lines_check_unique_ids():
    lines = [
        Line(line_id="L01", species="s", form="f", grade="g", annual_volume_kg=10),
        Line(line_id="L01", species="s2", form="f2", grade="g2", annual_volume_kg=20),
    ]
    failures = check_lines(RfxDraft(lines=lines))
    assert any("unique" in f for f in failures)


def test_terms_eval_weights_must_sum_to_100():
    terms = Terms(eval_weights=EvalWeights(price=60, quality=25, commercial=5), payment_terms="30 days")
    failures = check_terms(RfxDraft(terms=terms))
    assert any("90%, not 100%" in f for f in failures)


def test_terms_glaze_cap_required_for_glazed_species():
    lines = [Line(line_id="L17", species="Vannamei shrimp (farmed)", form="f", grade="g", annual_volume_kg=1)]
    terms = Terms(eval_weights=EvalWeights(price=60, quality=25, commercial=15), payment_terms="30 days")
    failures = check_terms(RfxDraft(lines=lines, terms=terms))
    assert any("glaze cap" in f for f in failures)


def test_questionnaire_requires_at_least_one():
    assert check_questionnaire(RfxDraft()) == ["At least one question is required"]


def test_questionnaire_pass_rule_valid_ref():
    from app.schemas.draft import PassRule

    q = Question(
        q_id="Q01",
        group="certifications",
        text="cert?",
        answer_type="text",
        pass_rule=PassRule(type="date_after", ref="not_a_real_field"),
    )
    failures = check_questionnaire(RfxDraft(questionnaire=[q]))
    assert any("unknown field" in f for f in failures)

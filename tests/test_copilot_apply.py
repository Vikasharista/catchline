from app.copilot.apply import apply_patch
from app.schemas.draft import RfxDraft, classify_risk

EMPTY_DRAFT = RfxDraft().model_dump()


def test_update_scalar_field():
    result = apply_patch(EMPTY_DRAFT, "scope", "update", "scope.currency", "EUR")
    assert result.ok
    assert result.draft["scope"]["currency"] == "EUR"


def test_add_line():
    line = {
        "line_id": "L01",
        "species": "Atlantic salmon (farmed)",
        "form": "HOG, frozen",
        "grade": "2-3 kg",
        "unit": "kg",
        "annual_volume_kg": 40000,
        "custom_fields": {},
    }
    result = apply_patch(EMPTY_DRAFT, "lines", "add", "lines", line)
    assert result.ok
    assert len(result.draft["lines"]) == 1
    assert result.draft["lines"][0]["line_id"] == "L01"


def test_update_line_field():
    draft = apply_patch(
        EMPTY_DRAFT,
        "lines",
        "add",
        "lines",
        {
            "line_id": "L01",
            "species": "Atlantic salmon (farmed)",
            "form": "HOG, frozen",
            "grade": "2-3 kg",
            "unit": "kg",
            "annual_volume_kg": 40000,
            "custom_fields": {},
        },
    ).draft
    result = apply_patch(draft, "lines", "update", "lines[L01].annual_volume_kg", 60000)
    assert result.ok
    assert result.draft["lines"][0]["annual_volume_kg"] == 60000


def test_remove_line():
    draft = apply_patch(
        EMPTY_DRAFT,
        "lines",
        "add",
        "lines",
        {
            "line_id": "L01",
            "species": "x",
            "form": "y",
            "grade": "z",
            "unit": "kg",
            "annual_volume_kg": 1,
            "custom_fields": {},
        },
    ).draft
    result = apply_patch(draft, "lines", "remove", "lines[L01]", None)
    assert result.ok
    assert result.draft["lines"] == []


def test_validation_failure_does_not_mutate():
    # negative volume fails validation? RfxDraft doesn't constrain >0 itself
    # (that's a sign-off check, not schema); use a genuinely invalid shape instead.
    result = apply_patch(EMPTY_DRAFT, "scope", "update", "scope.currency.nested", "oops")
    assert not result.ok
    assert result.draft is None


def test_risk_classification_money_or_eligibility():
    assert classify_risk("lines", "lines", "add") == "money_or_eligibility"
    assert classify_risk("lines", "lines[L01].annual_volume_kg", "update") == "money_or_eligibility"
    assert classify_risk("scope", "scope.currency", "update") == "money_or_eligibility"
    assert classify_risk("scope", "scope.weight_basis", "update") == "money_or_eligibility"
    assert classify_risk("terms", "terms.glaze_cap_pct", "update") == "money_or_eligibility"
    assert classify_risk("questionnaire", "questionnaire[Q01].pass_rule", "update") == "money_or_eligibility"


def test_risk_classification_normal():
    assert classify_risk("scope", "scope.title", "update") == "normal"
    assert classify_risk("lines", "lines[L01].spec_notes", "update") == "normal"
    assert classify_risk("terms", "terms.payment_terms", "update") == "normal"

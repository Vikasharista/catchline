from app.copilot.checks import check_lines, check_questionnaire, check_scope, check_terms
from app.copilot.reference_draft import reference_draft_dict
from app.schemas.draft import RfxDraft


def test_reference_draft_validates():
    draft = RfxDraft.model_validate(reference_draft_dict())
    assert len(draft.lines) == 30
    assert len(draft.questionnaire) == 12
    assert len(draft.suppliers) == 5


def test_reference_draft_signs_off_scope_lines_terms():
    draft = RfxDraft.model_validate(reference_draft_dict())
    assert check_scope(draft) == []
    assert check_lines(draft) == []
    assert check_terms(draft) == []
    assert check_questionnaire(draft) == []

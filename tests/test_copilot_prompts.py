"""Regression guard for a real bug: propose_change's `target` param had no
description at all, so the model had nothing to go on for the "add" op's
syntax and guessed an item id (e.g. "L31") instead of the bare list name
apply_patch actually expects ("lines") — every "add a line" proposal a
buyer accepted silently failed with "Malformed target". Found live while
testing the chat UI end to end; verified the fix by re-running the same
chat message and confirming the accept actually applied.
"""
from app.copilot.prompts import TOOL_SCHEMAS


def _propose_change_schema():
    return next(t for t in TOOL_SCHEMAS if t["function"]["name"] == "propose_change")


def test_propose_change_target_documents_add_uses_bare_list_name():
    target_param = _propose_change_schema()["function"]["parameters"]["properties"]["target"]
    description = target_param.get("description", "")
    assert description, "target must document its syntax or the model will guess wrong"
    assert "'lines'" in description or '"lines"' in description
    assert "add" in description.lower()


def test_propose_change_value_documents_questionnaire_item_shape():
    """Regression guard for a real bug: `value` had no description of what
    fields a questionnaire item needs, so the model invented plausible-
    sounding but wrong field names (question/category/required instead of
    the real text/group/answer_type). apply_patch doesn't validate an
    added item's shape, so every one of these accepts silently reached the
    DB, then failed Pydantic validation only when the buyer clicked Accept
    — which the frontend then showed as a green "Accepted" badge anyway,
    hiding that the questionnaire was never actually populated. Verified
    live: re-ran the same chat message after this fix and confirmed accept
    now returns status="accepted" with the item correctly in the draft.
    """
    value_param = _propose_change_schema()["function"]["parameters"]["properties"]["value"]
    description = value_param.get("description", "")
    assert description, "value must document each section's item shape or the model will guess wrong"
    for field in ("q_id", "group", "text", "answer_type"):
        assert field in description, f"questionnaire field {field!r} missing from value description"
    # the wrong field names the model actually used, that must NOT be
    # presented as valid — only mentioned (if at all) as what NOT to use
    assert "not exist on this schema" in description or "don't exist" in description

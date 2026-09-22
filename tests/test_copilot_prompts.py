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

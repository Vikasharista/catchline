"""Turns an accepted/edited ChangeProposal into a JSON patch on a copy of the
draft, validates it, and returns the result. Nothing else is allowed to touch
a draft (CLAUDE.md hard rule) — every write to an RfxDraft goes through here.

Target syntax:
  "scope.currency"              -> dotted path into a dict
  "lines[L01].annual_volume_kg" -> item in list `lines` whose id field
                                    (line_id/q_id/key) equals "L01", then a
                                    dotted path within it
  "lines"                        -> the list itself (for add/remove)

The list id field is inferred per section: line_id for lines, q_id for
questionnaire, key for custom_sections.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.schemas.draft import RfxDraft

_ID_FIELD = {"lines": "line_id", "questionnaire": "q_id", "custom_sections": "key"}
_TARGET_RE = re.compile(r"^([a-zA-Z_]+)(?:\[([^\]]+)\])?(?:\.(.+))?$")


@dataclass
class ApplyResult:
    draft: dict | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _set_nested(obj: dict, path: str, value) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = obj[part]
    obj[parts[-1]] = value


def _find_list_item(items: list[dict], id_field: str, id_value: str) -> dict | None:
    return next((item for item in items if item.get(id_field) == id_value), None)


def apply_patch(draft_dict: dict, section_key: str, op: str, target: str, value) -> ApplyResult:
    draft = {**draft_dict}  # shallow copy; we replace whole sub-structures below

    match = _TARGET_RE.match(target)
    if not match:
        return ApplyResult(draft=None, error=f"Malformed target: {target}")
    list_name, item_id, rest_path = match.groups()

    try:
        if list_name in _ID_FIELD:
            id_field = _ID_FIELD[list_name]
            items = list(draft.get(list_name, []))

            if op == "add":
                if item_id is not None:
                    return ApplyResult(draft=None, error="add op should not index an item")
                items = items + [value]
                draft[list_name] = items

            elif op == "remove":
                if item_id is None:
                    return ApplyResult(draft=None, error="remove op needs an indexed target")
                items = [i for i in items if i.get(id_field) != item_id]
                draft[list_name] = items

            elif op == "update":
                if item_id is None:
                    return ApplyResult(draft=None, error="update op on a list needs an indexed target")
                item = _find_list_item(items, id_field, item_id)
                if item is None:
                    return ApplyResult(draft=None, error=f"{list_name}[{item_id}] not found")
                item = {**item}
                if rest_path:
                    _set_nested(item, rest_path, value)
                else:
                    item = value
                items = [item if i.get(id_field) == item_id else i for i in items]
                draft[list_name] = items
            else:
                return ApplyResult(draft=None, error=f"Unknown op: {op}")
        else:
            # plain dotted path into a top-level dict section, e.g. "scope.currency"
            full_path = target
            section = {**draft.get(list_name, {})}
            draft[list_name] = section
            if op in ("add", "update"):
                _set_nested(draft, full_path, value)
            elif op == "remove":
                parts = full_path.split(".")
                obj = draft
                for part in parts[:-1]:
                    obj = obj[part]
                obj.pop(parts[-1], None)
            else:
                return ApplyResult(draft=None, error=f"Unknown op: {op}")

        RfxDraft.model_validate(draft)
        return ApplyResult(draft=draft)

    except (KeyError, TypeError, ValidationError) as exc:
        return ApplyResult(draft=None, error=str(exc))

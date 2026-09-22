SYSTEM_PROMPT = """You are the Catchline sourcing co-pilot. You help a buyer draft an RFx for frozen seafood by chatting with them.

Hard rules:
- Never invent volumes, prices or dates. Ask instead.
- Ask before assuming anything about weight basis, incoterm, currency, glaze cap, evaluation weights, award rules, or a line's volume — these are money or eligibility decisions.
- Label your own ideas as "suggested" — only propose what the buyer actually asked for as "from_you".
- Keep replies short and in plain language.
- Do not repeat a proposal the buyer has already rejected, unless they bring it up again.
- You cannot edit the draft yourself. Use propose_change or propose_section — the buyer must accept before anything changes. After proposing, say "I've suggested N changes", not "I've added..." or "I've changed...".
- Read the current draft with read_draft before proposing anything, so you don't repeat pending or already-applied changes.
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_draft",
            "description": "Returns the current draft JSON, each section's status, pending proposals, and the last 20 rejected proposals.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_change",
            "description": "Suggests an edit to an existing section. Does not write to the draft.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "op": {"type": "string", "enum": ["add", "update", "remove"]},
                    "target": {
                        "type": "string",
                        "description": (
                            "'add' on a list (lines/questionnaire/custom_sections): the bare list "
                            "name, e.g. 'lines' — value is the whole new item as an object, and "
                            "must include a new, unique id field (line_id for lines, q_id for "
                            "questionnaire, key for custom_sections). 'update'/'remove' on a "
                            "list item: 'lines[L01]' (index by line_id/q_id/key) — add "
                            "'.field_name' after the ']' for update to change just one field, e.g. "
                            "'lines[L01].annual_volume_kg'. A top-level dict section (scope/terms): "
                            "a dotted path, e.g. 'scope.currency'."
                        ),
                    },
                    "value": {},
                    "reason": {"type": "string"},
                    "origin": {"type": "string", "enum": ["from_you", "suggested"]},
                },
                "required": ["section", "op", "target", "value", "reason", "origin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_section",
            "description": "Suggests a new custom section. Does not write to the draft.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body_md": {"type": "string"},
                    "requires_supplier_response": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "origin": {"type": "string", "enum": ["from_you", "suggested"]},
                },
                "required": ["title", "body_md", "requires_supplier_response", "reason", "origin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask",
            "description": "Asks the buyer a clarifying question, optionally with quick-reply options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "allow_free_text": {"type": "boolean"},
                },
                "required": ["question", "allow_free_text"],
            },
        },
    },
]

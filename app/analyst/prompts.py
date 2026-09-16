SYSTEM_PROMPT = """You are the Catchline analyst. You answer a buyer's plain-English
questions about supplier quotes for a frozen-seafood RFx.

Hard rules:
- Use a tool for every number you state. Never state a number that didn't
  come from a tool result.
- Try the fixed tools first (coverage, uncertain_items, explain_cell,
  cheapest_per_line, split_award, what_if, price_spread,
  compare_last_year, make_chart, export_award, draft_memo). Use
  run_sandbox only for something they don't cover.
- Never guess an illegible or flagged value — name it as uncertain instead.
- If something isn't in this RFx at all (a species, a supplier), say
  "not in this RFx". Don't invent a plausible answer.
- Always say which suppliers or lines were excluded from a calculation,
  and why (not eligible, certificate expired, line blocked, etc).
- Keep the headline short; put the trail of what you checked in a
  separate "how I got this" note, not the main answer.
"""

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "coverage", "description": "Lines quoted per supplier; lines with fewer than 3 quotes.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "uncertain_items", "description": "Everything not confirmed, grouped by reason.", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "explain_cell",
            "description": "Source, steps, flags for one supplier/line cell.",
            "parameters": {
                "type": "object",
                "properties": {"supplier_id": {"type": "string"}, "line_id": {"type": "string"}},
                "required": ["supplier_id", "line_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cheapest_per_line",
            "description": "Award table, total spend, winners by supplier, uncovered lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "eligible_only": {"type": "boolean"},
                    "exclude_suppliers": {"type": "array", "items": {"type": "string"}},
                    "species": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "split_award",
            "description": "Greedy cheapest-first split respecting a max share per supplier per species.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_share_per_supplier_per_species": {"type": "number"},
                    "eligible_only": {"type": "boolean"},
                },
                "required": ["max_share_per_supplier_per_species"],
            },
        },
    },
    {"type": "function", "function": {"name": "price_spread", "description": "Per line: min, max, spread %.", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "compare_last_year",
            "description": "Comparison only on lines that have history.",
            "parameters": {"type": "object", "properties": {"supplier_id": {"type": "string"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sandbox",
            "description": "Runs a read-only pandas expression against the `quotes` DataFrame for anything the fixed tools don't cover. No imports, no dunder access, 5s timeout, 500-row cap.",
            "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
        },
    },
]

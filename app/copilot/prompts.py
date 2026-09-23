from app.knowledge.glossary import glossary_context

SYSTEM_PROMPT = """You are the Catchline sourcing co-pilot. You help a buyer draft an RFx for frozen seafood by chatting with them.

A new RFx starts with an empty draft — no lines, no questionnaire, no terms.
It fills in across four sections, in this order of priority when you're the
one choosing what to ask about next:
1. Scope — product/category, buyer site, contract start/end, incoterm +
   place, currency, weight basis, response deadline, award date.
2. Lines — species, form, grade, and annual volume for each line item.
3. Questionnaire — which supplier questions to ask (certifications, quality,
   traceability, commercial); suggest a sensible default set if the buyer
   doesn't have opinions, but let them confirm or edit it.
4. Terms — payment terms, glaze cap, quote validity, evaluation weights,
   award rules.
Always read_draft first to see what's already filled in (from earlier turns,
or the buyer copy-pasting several sections at once) and only ask about what's
genuinely still missing — don't re-ask for something already on the draft.

First, work out what the buyer's message actually is before deciding what to
do — don't default to running the intake script on every message:
- They gave you facts (a species, a volume, a place, a date, anything
  concrete) → propose_change/propose_section with exactly that, immediately.
  Never hold a fact back waiting for the rest of "its" section to be
  complete — a message with only a volume still gets proposed as a partial
  line/field; ask about what's still missing in the same reply, don't make
  them repeat what they already gave you.
- They asked a question (what does a term mean, what's typical/reasonable,
  why do you need a field, what should I put) → answer it directly, using
  the glossary/precedent reference below when it's covered there. Only after
  actually answering, and only if it's natural, follow up with the next
  thing still missing from the draft. Never respond to a question with only
  your own unrelated checklist question — that reads as not having listened.
- They're undecided or ask for a recommendation → give one, labeled clearly
  as a suggestion (or as Nordcap's own past precedent when the glossary below
  has it), and say they can accept, edit, or ignore it. Don't just ask them
  to decide with no input from you. Stick to the reference below for any
  specific number — do not add other figures/stats of your own (e.g. a
  "typical range" for a species) that aren't in it; if the reference doesn't
  cover it, say plainly that you don't have a number for that and suggest
  they confirm with suppliers, rather than presenting a guess as if it were
  known. If the reference has a precedent for a different item than what
  they asked about (e.g. it gives a glaze cap for shrimp/squid but they
  asked about salmon), don't adjust, interpolate or "tighten" it into a new
  number for their item — state the precedent exactly as given, say plainly
  it wasn't set for this item specifically, and offer it only as "you could
  reuse the same figure for consistency" or suggest confirming with
  suppliers, never as a derived recommendation with your own number in it.

Reference (use to answer questions and inform suggestions — never assume it
applies to the buyer's own new RFx without them confirming):
{glossary}

Hard rules:
- Never invent volumes, prices or dates. Ask instead.
- Never invent a "typical" or "usual" number (a glaze %, a lead time, a price range, anything) that isn't in the reference block below — that's the same kind of invented business data as a volume or price, just dressed up as general knowledge.
- Ask before assuming anything about weight basis, incoterm, currency, glaze cap, evaluation weights, award rules, or a line's volume — these are money or eligibility decisions. Answering a question about what a term means or what's typical is not the same as assuming a value for this RFx — do that freely.
- Label your own ideas as "suggested" — only propose what the buyer actually asked for as "from_you".
- Keep replies short and in plain language.
- Do not repeat a proposal the buyer has already rejected, unless they bring it up again.
- You cannot edit the draft yourself. Use propose_change or propose_section — the buyer must accept before anything changes. After proposing, say "I've suggested N changes", not "I've added..." or "I've changed...".
- Read the current draft with read_draft before proposing anything, so you don't repeat pending or already-applied changes.
""".format(glossary=glossary_context())

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
                    "value": {
                        "description": (
                            "Field names must match the draft schema exactly — an unrecognized "
                            "field name is silently dropped and a missing required one fails "
                            "validation when the buyer accepts (they see a generic error, not what "
                            "field was wrong), so get this right rather than guessing.\n"
                            "- lines item: {line_id, species, form, grade, spec_notes (optional), "
                            "unit (default 'kg'), annual_volume_kg, custom_fields (optional object)}.\n"
                            "- questionnaire item: {q_id, group: one of "
                            "certifications|quality|traceability|commercial, text, answer_type: one "
                            "of yes_no|text|date|file, pass_rule (optional {scope, condition})}. Not "
                            "'question'/'category'/'required' — those field names don't exist on "
                            "this schema.\n"
                            "- custom_sections item: {key, title, body_md, "
                            "requires_supplier_response}.\n"
                            "- scope.* update: value is just the new field's value (a string/etc, "
                            "not an object) — fields are title, category, buyer_site, "
                            "contract_start, contract_end, incoterm, incoterm_place, currency, "
                            "weight_basis, response_deadline, award_date.\n"
                            "- terms.* update: value is the new field's value — fields are "
                            "payment_terms, glaze_cap_pct, quote_validity_days, "
                            "partial_quotes_allowed, eval_weights ({price, quality, commercial}, "
                            "each 0-100 summing to 100), award_rules (list of {type, value, "
                            "schemes, codes, applies_to})."
                        )
                    },
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

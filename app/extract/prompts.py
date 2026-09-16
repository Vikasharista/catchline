PROMPT_VERSION = "v1"

PASS_A_SYSTEM = """You extract prices and terms from a frozen-seafood supplier's RFx reply.

Rules, no exceptions:
- Read every number exactly as written in the source. Never convert currency, units, or weight basis — that happens later in code.
- If a value cannot be read (stained, cropped, illegible), set price to null and legibility to "illegible". Never guess a plausible number.
- For every item, quote the exact source text in raw_text and give a locator (cell, page, paragraph/table index, or image region).
- If the document states a default that applies to several items (e.g. "all prices CFR Le Havre in USD", "20% glaze on gross weight"), apply it to every item it covers and say so in that item's raw_text or product_desc.
- Capture discounts, rebates and surcharges in conditions[] with their scope — do not fold them into price.
- Capture questionnaire answers if present, each with its own raw_text and locator.
- Output must match the given JSON schema exactly. No commentary outside the JSON.
"""

PASS_B_SYSTEM = """You match extracted price items to RFx line items by species, form and grade.

Rules:
- Match on species + form + grade similarity, not on price.
- Give a short match_reason for every match (or non-match).
- If an item doesn't correspond to any RFx line, set line_id to null and explain why in match_reason.
- Give a match_confidence between 0 and 1. Anything below 0.7 should be treated as needing buyer review downstream — that's not your job, just report the number honestly.
- Output must match the given JSON schema exactly. No commentary outside the JSON.
"""


def build_pass_a_messages(document_text: str, images_b64: list[str], rfx_context: str) -> list[dict]:
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"RFx line items (species/form/grade reference, for context only):\n{rfx_context}\n\n"
                f"Document content:\n{document_text}"
            ),
        }
    ]
    for b64 in images_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    return [
        {"role": "system", "content": PASS_A_SYSTEM},
        {"role": "user", "content": content},
    ]


def build_pass_b_messages(items_json: str, rfx_lines_json: str) -> list[dict]:
    return [
        {"role": "system", "content": PASS_B_SYSTEM},
        {
            "role": "user",
            "content": f"Extracted items:\n{items_json}\n\nRFx lines:\n{rfx_lines_json}",
        },
    ]

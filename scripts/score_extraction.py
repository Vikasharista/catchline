"""Scores live extraction against the answer key (PRD §7.4, §11).

Never imported by app code — this is the one place allowed to read
data/seed/05_answer_key/, and only for scoring, never as an LLM input.

Usage: python scripts/score_extraction.py [--live]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from app.extract.agent import extract_pass_a, extract_pass_b
from app.ingest.router import route
from app.normalize.convert import NormalizeInput, convert

SEED = Path("data/seed/aerchain_fish_rfx_dataset")
REPLIES_DIR = SEED / "02_supplier_replies"
ANSWER_KEY = SEED / "05_answer_key" / "ground_truth_quotes.csv"

SUPPLIER_FILES = {
    "S1": "S1_Fjordline_quotation.xlsx",
    "S2": "S2_PacificRim_offer.pdf",
    "S3": "S3_AtlanticoPesca_propuesta.docx",
    "S4": "S4_Oceanis_ratecard_photo.jpg",
    "S5": "S5_BalticBlue_reply.eml",
}

SUPPLIER_NAMES = {
    "S1": "Fjordline Seafood AS",
    "S2": "Pacific Rim Seafoods Ltd",
    "S3": "Atlantico Pesca S.L.",
    "S4": "Oceanis Trading SARL",
    "S5": "Baltic Blue Foods Sp. z o.o.",
}


def _load_answer_key() -> dict[tuple[str, str], dict]:
    rows: dict[tuple[str, str], dict] = {}
    with open(ANSWER_KEY, newline="") as f:
        for row in csv.DictReader(f):
            rows[(row["supplier"], row["line"])] = row
    return rows


def _rfx_context(answer_key: dict[tuple[str, str], dict]) -> tuple[str, list[dict]]:
    """Species/form/grade per line, for prompt context and line matching —
    never the price columns.
    """
    seen: dict[str, dict] = {}
    for (_, line), row in answer_key.items():
        if line not in seen:
            seen[line] = {
                "line_id": line,
                "species": row["species"],
                "form": row["form"],
                "grade": row["grade"],
            }
    lines = [seen[k] for k in sorted(seen)]
    text = "\n".join(f"{l['line_id']}: {l['species']}, {l['form']}, {l['grade']}" for l in lines)
    return text, lines


def score(live: bool = False) -> None:
    answer_key = _load_answer_key()
    rfx_context, rfx_lines = _rfx_context(answer_key)

    exact = flagged = silently_wrong = 0
    total = 0

    for supplier_code, filename in SUPPLIER_FILES.items():
        path = REPLIES_DIR / filename
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        doc = route(path)

        extraction, needs_attention = extract_pass_a(doc, sha256=sha256, rfx_context=rfx_context, live=live)
        if extraction is None:
            print(f"{supplier_code}: extraction failed (needs_attention)")
            continue

        matches = extract_pass_b(extraction, rfx_lines, sha256=sha256, live=live)
        match_by_item = {m.item_index: m for m in matches.matches}

        supplier_name = SUPPLIER_NAMES[supplier_code]
        for i, item in enumerate(extraction.items):
            match = match_by_item.get(i)
            if match is None or match.line_id is None:
                continue
            key = (supplier_code, match.line_id)
            if key not in answer_key:
                continue
            total += 1
            expected = float(answer_key[key]["eur_per_kg_net_dap"])

            norm_input = NormalizeInput(
                supplier_name=supplier_name,
                line_id=match.line_id,
                price=item.price,
                currency=item.currency or extraction.currency or "EUR",
                price_unit=item.price_unit or "per_kg",
                pack_size_kg=item.pack_size_kg,
                weight_basis=item.weight_basis,
                glaze_pct=item.glaze_pct,
                incoterm=item.incoterm or extraction.incoterm,
                incoterm_place=item.incoterm_place or extraction.incoterm_place,
                references_prior=item.references_prior,
            )
            result = convert(norm_input)

            if result.eur_kg_net_dap is None or item.legibility == "illegible":
                flagged += 1
            elif abs(result.eur_kg_net_dap - expected) / expected <= 0.01:
                exact += 1
            elif result.flags:
                flagged += 1
            else:
                silently_wrong += 1
                print(
                    f"SILENTLY WRONG: {supplier_code}/{match.line_id} "
                    f"expected {expected}, got {result.eur_kg_net_dap}"
                )

    print(f"\n{total} cells matched · {exact} exact · {flagged} flagged · {silently_wrong} silently wrong")
    print(f"Pass bar (0 silently wrong): {'PASS' if silently_wrong == 0 else 'FAIL'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="bypass the LLM cache")
    args = parser.parse_args()
    score(live=args.live)

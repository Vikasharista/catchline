"""Acceptance test from PRD §7.5: unit tests reproduce eur_per_kg_net_dap for
EVERY row of ground_truth_quotes.csv within +/-0.01, given the answer key's
native fields. This never touches the LLM — it only exercises app/normalize/.
"""
import csv
import re
from pathlib import Path

import pytest

from app.normalize.convert import NormalizeInput, convert

ANSWER_KEY = (
    Path(__file__).parent.parent
    / "data/seed/aerchain_fish_rfx_dataset/05_answer_key/ground_truth_quotes.csv"
)

SUPPLIER_NAMES = {
    "S1": "Fjordline Seafood AS",
    "S2": "Pacific Rim Seafoods Ltd",
    "S3": "Atlantico Pesca S.L.",
    "S4": "Oceanis Trading SARL",
    "S5": "Baltic Blue Foods Sp. z o.o.",
}


def _price_unit(native_unit: str) -> str:
    if "/lb" in native_unit:
        return "per_lb"
    if "/block" in native_unit:
        return "per_block"
    if "/carton" in native_unit:
        return "per_carton"
    if "/MC" in native_unit:
        return "per_master_carton"
    return "per_kg"


def _parse_incoterm(raw: str) -> tuple[str, str, float | None]:
    """"FCA Alesund" -> ("FCA", "Alesund", None); "EXW Gdynia + 0.18" -> ("EXW", "Gdynia", 0.18)."""
    m = re.match(r"^(\S+)\s+(.*?)(?:\s*\+\s*([\d.]+))?$", raw)
    incoterm, place, extra = m.group(1), m.group(2).strip(), m.group(3)
    return incoterm, place, float(extra) if extra else None


def _load_rows():
    with open(ANSWER_KEY, newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("row", _load_rows(), ids=lambda r: f"{r['supplier']}-{r['line']}")
def test_convert_matches_answer_key(row):
    supplier_name = SUPPLIER_NAMES[row["supplier"]]
    incoterm, place, supplier_freight = _parse_incoterm(row["incoterm"])
    net_fraction = float(row["net_fraction"])
    references_prior = row["source"].startswith("same as last year")

    item = NormalizeInput(
        supplier_name=supplier_name,
        line_id=row["line"],
        price=float(row["native_price"]),
        currency=row["currency"],
        price_unit=_price_unit(row["native_unit"]),
        pack_size_kg=float(row["kg_per_unit"]) if row["kg_per_unit"] else None,
        weight_basis="net" if net_fraction == 1.0 else "gross",
        glaze_pct=round(1 - net_fraction, 4) if net_fraction != 1.0 else None,
        incoterm=incoterm,
        incoterm_place=place,
        supplier_stated_freight=supplier_freight if row["source"] == "quoted" else None,
        references_prior=references_prior,
    )

    result = convert(item)
    expected = float(row["eur_per_kg_net_dap"])

    assert result.eur_kg_net_dap is not None, f"{row['supplier']}/{row['line']}: got no value, flags={result.flags}"
    assert result.eur_kg_net_dap == pytest.approx(expected, abs=0.011), (
        f"{row['supplier']}/{row['line']}: expected {expected}, got {result.eur_kg_net_dap}, "
        f"steps={result.steps}"
    )


def test_worked_example_s2_l18():
    """PRD §7.5 worked example: S2 L18 $3.74/lb -> 8.93 EUR/kg net DAP."""
    item = NormalizeInput(
        supplier_name="Pacific Rim Seafoods Ltd",
        line_id="L18",
        price=3.74,
        currency="USD",
        price_unit="per_lb",
        weight_basis="gross",
        glaze_pct=0.2,
        incoterm="CFR",
        incoterm_place="Le Havre",
    )
    result = convert(item)
    assert result.eur_kg_net_dap == pytest.approx(8.93, abs=0.01)

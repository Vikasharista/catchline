"""Loads the buyer's fixed reference tables (PRD §6/§7.5). Pure data access —
no conversion logic here.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import openpyxl

from app.config import settings

SEED_DIR = settings.data_dir / "seed" / "aerchain_fish_rfx_dataset" / "04_buyer_reference_data"


@lru_cache
def load_fx_rates(path: Path | None = None) -> dict[str, float]:
    """Returns {currency: units_per_EUR}, e.g. {"USD": 1.17, "NOK": 11.7}."""
    path = path or SEED_DIR / "fx_rates_2026-09-10.csv"
    rates: dict[str, float] = {"EUR": 1.0}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rates[row["currency"]] = float(row["units_per_EUR"])
    return rates


@lru_cache
def load_freight_adders(path: Path | None = None) -> dict[str, float]:
    """Returns {"FCA Alesund": 0.35, "CFR Le Havre": 0.12, ...}. DAP Boulogne is 0."""
    path = path or SEED_DIR / "freight_adders_to_DAP_Boulogne.csv"
    adders: dict[str, float] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            value = row["eur_per_kg"].strip()
            if value:
                adders[row["incoterm_origin"]] = float(value)
    return adders


@lru_cache
def load_last_year_prices(path: Path | None = None) -> dict[tuple[str, str], float]:
    """Returns {(supplier_name, line_id): eur_kg_net_dap} from last year's contract."""
    path = path or SEED_DIR / "last_year_contract_prices.xlsx"
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header, *data = rows
    idx = {name: i for i, name in enumerate(header)}
    result: dict[tuple[str, str], float] = {}
    for row in data:
        if row[idx["Supplier"]] is None:
            continue
        supplier = row[idx["Supplier"]]
        line = row[idx["Line"]]
        price = row[idx["EUR/kg net DAP"]]
        result[(supplier, line)] = float(price)
    return result

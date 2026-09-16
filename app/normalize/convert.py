"""Deterministic price normalization to EUR/kg net weight, DAP Boulogne.

Per CLAUDE.md: the LLM never produces a number that is displayed. This module
is the only place that computes eur_kg_net_dap. Every step is recorded so the
UI can show a full trail from the source quote to the comparable price
(PRD §7.5).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.normalize.reference import load_fx_rates, load_freight_adders, load_last_year_prices

LB_TO_KG = 0.45359237


@dataclass
class NormalizeInput:
    supplier_name: str
    line_id: str
    price: float | None
    currency: str
    price_unit: str  # per_kg | per_lb | per_block | per_carton | per_master_carton
    pack_size_kg: float | None = None
    weight_basis: str = "net"  # net | gross | unknown
    glaze_pct: float | None = None
    incoterm: str | None = None
    incoterm_place: str | None = None
    supplier_stated_freight: float | None = None
    references_prior: bool = False


@dataclass
class NormalizeResult:
    eur_kg_net_dap: float | None
    steps: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def add_step(self, label: str, operation: str, value) -> None:
        self.steps.append({"label": label, "operation": operation, "value": value})

    def add_flag(self, code: str) -> None:
        if code not in self.flags:
            self.flags.append(code)


def _incoterm_key(incoterm: str | None, place: str | None) -> str | None:
    if not incoterm or not place:
        return None
    return f"{incoterm} {place}"


def convert(item: NormalizeInput) -> NormalizeResult:
    result = NormalizeResult(eur_kg_net_dap=None)

    # "Same as last year" short-circuits the whole pipeline: the contract
    # file's price is already EUR/kg net DAP (PRD §7.5 step 5).
    if item.references_prior:
        last_year = load_last_year_prices()
        price = last_year.get((item.supplier_name, item.line_id))
        if price is None:
            result.add_flag("prior_not_found")
            return result
        result.eur_kg_net_dap = price
        result.add_step("Same as last year", "lookup", price)
        result.add_flag("inferred_prior")
        if item.supplier_stated_freight is not None:
            # supplier also mentions freight on top of "same as last year" —
            # ambiguous whether it applies; don't apply it, just flag it.
            result.add_flag("freight_ambiguous")
        return result

    if item.price is None:
        result.add_flag("illegible")
        return result

    value = item.price

    # 1. Unit to per kg
    if item.price_unit == "per_kg":
        pass
    elif item.price_unit == "per_lb":
        value = value / LB_TO_KG
        result.add_step("Unit: per lb to per kg", "divide", LB_TO_KG)
    elif item.price_unit in ("per_block", "per_carton", "per_master_carton"):
        if not item.pack_size_kg:
            result.add_flag("unit_unknown")
            return result
        value = value / item.pack_size_kg
        result.add_step(f"Unit: {item.price_unit} ({item.pack_size_kg} kg) to per kg", "divide", item.pack_size_kg)
    else:
        result.add_flag("unit_unknown")
        return result

    # 2. FX
    fx_rates = load_fx_rates()
    rate = fx_rates.get(item.currency)
    if rate is None:
        result.add_flag("unit_unknown")
        return result
    if rate != 1.0:
        value = value / rate
        result.add_step(f"FX: {item.currency} to EUR", "divide", rate)

    # 3. Glaze
    if item.weight_basis == "gross" and item.glaze_pct:
        net_fraction = 1 - item.glaze_pct
        value = value / net_fraction
        result.add_step(f"Glaze: {item.glaze_pct:.0%} on gross weight", "divide", round(net_fraction, 4))
        result.add_flag("glaze_adjusted")
    elif item.weight_basis == "unknown" and item.glaze_pct:
        result.add_flag("glaze_basis_unknown")

    # 4. Freight to DAP Boulogne
    freight_adders = load_freight_adders()
    key = _incoterm_key(item.incoterm, item.incoterm_place)
    if item.supplier_stated_freight is not None:
        adder = item.supplier_stated_freight
        result.add_flag("supplier_stated_approx")
    elif key and key in freight_adders:
        adder = freight_adders[key]
    elif item.incoterm == "DAP":
        adder = 0.0
    else:
        result.add_flag("freight_ambiguous")
        adder = 0.0

    if adder:
        value = value + adder
        result.add_step(f"Freight to DAP Boulogne ({key or item.incoterm})", "add", adder)
    result.add_flag("fx_converted") if item.currency != "EUR" else None
    result.add_flag("unit_converted") if item.price_unit != "per_kg" else None
    result.add_flag("freight_assumed") if adder else None

    result.eur_kg_net_dap = round(value, 3)
    return result

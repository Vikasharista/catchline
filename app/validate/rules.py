"""Rule-based flags (PRD §7.6). Flags from the normaliser's own steps
(illegible, unit_unknown, glaze_basis_unknown, freight_ambiguous,
inferred_prior, glaze_adjusted, fx_converted, unit_converted,
freight_assumed, supplier_stated_approx) are already emitted by
app.normalize.convert.convert() — this module adds the flags that need
context across rows: peer/last-year outliers, low confidence, missing
lines, and unmatched items.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.normalize.reference import load_last_year_prices

SEVERITY = {
    "illegible": "red",
    "prior_not_found": "red",
    "unit_unknown": "amber",
    "glaze_basis_unknown": "amber",
    "freight_ambiguous": "amber",
    "inferred_prior": "amber",
    "peer_outlier": "amber",
    "ly_outlier": "amber",
    "low_confidence": "amber",
    "glaze_adjusted": "info",
    "fx_converted": "info",
    "unit_converted": "info",
    "freight_assumed": "info",
    "supplier_stated_approx": "info",
    "not_quoted": "info",
    "unmatched_item": "info",
}

PEER_OUTLIER_THRESHOLD = 0.25
LY_OUTLIER_THRESHOLD = 0.20
LOW_CONFIDENCE_THRESHOLD = 0.8


def severity_of(code: str) -> str:
    return SEVERITY.get(code, "info")


@dataclass
class QuoteRow:
    supplier_id: str
    supplier_name: str
    line_id: str
    eur_kg_net_dap: float | None
    confidence: float = 1.0


@dataclass
class RuleFlag:
    code: str
    severity: str
    supplier_id: str
    line_id: str
    message: str


def peer_outlier_flags(quotes: list[QuoteRow]) -> list[RuleFlag]:
    flags: list[RuleFlag] = []
    by_line: dict[str, list[QuoteRow]] = {}
    for q in quotes:
        if q.eur_kg_net_dap is not None:
            by_line.setdefault(q.line_id, []).append(q)

    for line_id, rows in by_line.items():
        if len(rows) < 2:
            continue
        values = [r.eur_kg_net_dap for r in rows]
        median = statistics.median(values)
        if median == 0:
            continue
        for r in rows:
            deviation = abs(r.eur_kg_net_dap - median) / median
            if deviation > PEER_OUTLIER_THRESHOLD:
                flags.append(
                    RuleFlag(
                        code="peer_outlier",
                        severity=severity_of("peer_outlier"),
                        supplier_id=r.supplier_id,
                        line_id=line_id,
                        message=f"{deviation:.0%} from the median of other suppliers on {line_id}",
                    )
                )
    return flags


def last_year_outlier_flags(quotes: list[QuoteRow]) -> list[RuleFlag]:
    last_year = load_last_year_prices()
    flags: list[RuleFlag] = []
    for q in quotes:
        if q.eur_kg_net_dap is None:
            continue
        prior = last_year.get((q.supplier_name, q.line_id))
        if prior is None or prior == 0:
            continue
        deviation = abs(q.eur_kg_net_dap - prior) / prior
        if deviation > LY_OUTLIER_THRESHOLD:
            flags.append(
                RuleFlag(
                    code="ly_outlier",
                    severity=severity_of("ly_outlier"),
                    supplier_id=q.supplier_id,
                    line_id=q.line_id,
                    message=f"{deviation:.0%} from last year's price ({prior} EUR/kg)",
                )
            )
    return flags


def low_confidence_flags(quotes: list[QuoteRow]) -> list[RuleFlag]:
    return [
        RuleFlag(
            code="low_confidence",
            severity=severity_of("low_confidence"),
            supplier_id=q.supplier_id,
            line_id=q.line_id,
            message=f"Extraction confidence {q.confidence:.2f}",
        )
        for q in quotes
        if q.confidence < LOW_CONFIDENCE_THRESHOLD
    ]


def not_quoted_flags(quotes: list[QuoteRow], all_line_ids: list[str], supplier_ids: list[str]) -> list[RuleFlag]:
    quoted = {(q.supplier_id, q.line_id) for q in quotes}
    flags = []
    for supplier_id in supplier_ids:
        for line_id in all_line_ids:
            if (supplier_id, line_id) not in quoted:
                flags.append(
                    RuleFlag(
                        code="not_quoted",
                        severity=severity_of("not_quoted"),
                        supplier_id=supplier_id,
                        line_id=line_id,
                        message=f"{line_id} missing from this supplier's reply",
                    )
                )
    return flags


def apply_rules(
    quotes: list[QuoteRow],
    all_line_ids: list[str],
    supplier_ids: list[str],
) -> list[RuleFlag]:
    return [
        *peer_outlier_flags(quotes),
        *last_year_outlier_flags(quotes),
        *low_confidence_flags(quotes),
        *not_quoted_flags(quotes, all_line_ids, supplier_ids),
    ]

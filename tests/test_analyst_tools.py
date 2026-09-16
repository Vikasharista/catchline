import pandas as pd
import pytest

from app.analyst.sandbox import SandboxError, run_sandbox
from app.analyst.tools import AnalystTools

ROWS = [
    # line_id, species, supplier_id, supplier_name, eur_kg_net_dap, status, eligibility, line_blocked, volume_kg
    ("L01", "salmon", "S1", "Sup1", 7.25, "confirmed", "eligible", False, 40000),
    ("L01", "salmon", "S4", "Sup4", 7.15, "confirmed", "not_eligible", False, 40000),
    ("L02", "cod", "S1", "Sup1", 6.08, "confirmed", "eligible", False, 20000),
    ("L02", "cod", "S3", "Sup3", 6.23, "confirmed", "eligible", False, 20000),
    ("L03", "shrimp", "S2", "Sup2", 8.93, "flagged", "conditional", True, 15000),
    ("L03", "shrimp", "S3", "Sup3", 9.49, "confirmed", "eligible", False, 15000),
]

COLUMNS = [
    "line_id",
    "species",
    "supplier_id",
    "supplier_name",
    "eur_kg_net_dap",
    "status",
    "eligibility",
    "line_blocked",
    "volume_kg",
]


def _df():
    df = pd.DataFrame(ROWS, columns=COLUMNS)
    df["native_price"] = None
    df["native_unit"] = None
    df["currency"] = "EUR"
    df["incoterm"] = "DAP"
    df["flags"] = [[] for _ in range(len(df))]
    df["conditions"] = [[] for _ in range(len(df))]
    return df


def test_coverage():
    tools = AnalystTools(_df(), all_line_ids=["L01", "L02", "L03", "L04"], all_supplier_ids=["S1", "S2", "S3", "S4"])
    result = tools.coverage()
    assert result["lines_quoted_per_supplier"]["S1"] == 2
    assert result["lines_quoted_per_supplier"]["S4"] == 1
    assert "L04" in result["lines_with_fewer_than_3_quotes"]  # no quotes at all


def test_explain_cell():
    tools = AnalystTools(_df(), all_line_ids=["L01"], all_supplier_ids=["S1"])
    result = tools.explain_cell("S1", "L01")
    assert result["found"] is True
    assert result["eur_kg_net_dap"] == 7.25

    missing = tools.explain_cell("S9", "L99")
    assert missing["found"] is False


def test_cheapest_per_line_eligible_only_excludes_not_eligible_and_blocked():
    tools = AnalystTools(_df(), all_line_ids=["L01", "L02", "L03"], all_supplier_ids=["S1", "S2", "S3", "S4"])
    result = tools.cheapest_per_line(eligible_only=True)
    winners = {row["line_id"]: row["supplier_id"] for row in result["award_table"]}
    assert winners["L01"] == "S1"  # S4 cheaper but not eligible
    assert winners["L03"] == "S3"  # S2 cheaper but line_blocked


def test_price_spread_sorted_descending():
    tools = AnalystTools(_df(), all_line_ids=["L01", "L02", "L03"], all_supplier_ids=["S1", "S2", "S3", "S4"])
    result = tools.price_spread()
    spreads = [line["spread_pct"] for line in result["lines"]]
    assert spreads == sorted(spreads, reverse=True)


def test_sandbox_basic_expression():
    tables = {"quotes": _df()}
    result = run_sandbox("quotes['eur_kg_net_dap'].mean()", tables)
    assert result == pytest.approx(_df()["eur_kg_net_dap"].mean())


def test_sandbox_blocks_imports():
    with pytest.raises(SandboxError):
        run_sandbox("__import__('os').system('echo hi')", {"quotes": _df()})


def test_sandbox_blocks_dunder():
    with pytest.raises(SandboxError):
        run_sandbox("quotes.__class__", {"quotes": _df()})

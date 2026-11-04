"""Impossible values are found and shown first; Excel row numbers match the file; the sandbox runs without Unix-only modules."""
import numpy as np
import openpyxl
import pandas as pd
from alpha_engine import pipeline
from alpha_engine.investigate import sandbox
from alpha_engine.understand.reader import read_any


def _shop(n=600, bad=60, seed=3):
    r = np.random.default_rng(seed)
    qty = r.integers(1, 20, n)
    price = r.choice([5.0, 12.0, 40.0, 150.0], n)
    sales = np.round(qty * price, 2)
    profit = np.round(sales * r.uniform(-0.2, 0.3, n), 2)
    profit[:bad] = np.round(sales[:bad] * 4.5, 2)                       # impossible: profit 4.5x the sale
    return pd.DataFrame({"Order Date": pd.date_range("2023-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
                         "Category": r.choice(["Tea", "Coffee", "Snacks"], n), "Qty": qty, "Unit Price": price,
                         "Sales": sales, "Profit": profit})


def test_profit_above_sale_is_flagged_and_leads(tmp_path):
    df = _shop()
    p = tmp_path / "shop.csv"; df.to_csv(p, index=False)
    rep = pipeline.analyze("v1", [{"name": "shop.csv", "path": str(p)}], {}, str(tmp_path / "data"), None)
    probs = [i for i in rep["insights"]["items"] if i["type"] == "data_problem"]
    assert probs and probs[0]["numbers"]["rows"] == 60
    n = probs[0]["numbers"]
    assert abs(n["profit_on_rows"] - df.Profit[:60].sum()) < 0.01
    assert abs(n["profit_without"] - df.Profit[60:].sum()) < 0.01
    assert rep["briefing"]["headline"].startswith("Check your data first")
    assert rep["insights"]["items"][0]["type"] == "data_problem"
    rows = probs[0]["evidence"]["rows"]
    assert all(r[0] - 2 < 60 for r in rows)                             # source rows point at the bad lines (file row = index + 2)
    tiles = {t["metric"]: t["value"] for t in rep["overview"]["tiles"]}
    assert abs(tiles["profit"] - df.Profit.sum()) < 0.01                # nothing is silently removed


def test_clean_file_has_no_data_problem(tmp_path):
    df = _shop(bad=0)
    p = tmp_path / "shop.csv"; df.to_csv(p, index=False)
    rep = pipeline.analyze("v2", [{"name": "shop.csv", "path": str(p)}], {}, str(tmp_path / "data"), None)
    assert not [i for i in rep["insights"]["items"] if i["type"] == "data_problem"]
    assert not rep["briefing"]["headline"].startswith("Check your data first")


def test_excel_row_numbers_match_the_sheet(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Monthly sales"]); ws.append([]); ws.append(["Date", "Item", "Amount"])
    ws.append(["2024-01-01", "A", 10]); ws.append(["2024-01-02", "B", 20]); ws.append([]); ws.append(["2024-01-03", "C", 30])
    p = tmp_path / "m.xlsx"; wb.save(p)
    df, _ = read_any(str(p))
    assert df.set_index("Item")["_row"].to_dict() == {"A": 4, "B": 5, "C": 7}
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Date", "Amount"]); ws.append(["2024-01-01", 1]); ws.append(["2024-01-02", 2])
    p2 = tmp_path / "plain.xlsx"; wb.save(p2)
    assert read_any(str(p2))[0]["_row"].tolist() == [2, 3]


def test_sandbox_runs_where_resource_is_missing(monkeypatch):
    # Windows has no 'resource' module: simulate that by making the import fail inside the child process
    monkeypatch.setattr(sandbox, "RUNNER", sandbox.RUNNER.replace("import resource ", "import resource_not_on_this_os as resource "))
    out = sandbox.run("result = int(df['x'].sum())", pd.DataFrame({"x": [1, 2, 3]}))
    assert out == {"ok": True, "result": 6}


def test_sandbox_allows_small_functions_but_not_imports():
    out = sandbox.run("def top(s):\n    return s.sort_values().tail(1).tolist()\nresult = top(df['x'])", pd.DataFrame({"x": [3, 9, 1]}))
    assert out["ok"] and out["result"] == [9]
    assert not sandbox.run("import os\nresult = 1", pd.DataFrame({"x": [1]}))["ok"]

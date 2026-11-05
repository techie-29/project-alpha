"""Multi-sheet workbooks and the header rules that real business exports need. All data here is made up for the test;
nothing is tied to one business or one file."""
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_engine import pipeline
from alpha_engine.understand.reader import table_sheets
from alpha_engine.understand.prepare import prepare
from alpha_engine.model.infer import infer_table
from alpha_engine.metrics.catalogue import available

R = np.random.default_rng(5)


def _book(path: Path, sheets: dict) -> None:
    with pd.ExcelWriter(path) as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)


def _business(n=1500):
    r = np.random.default_rng(5)                 # the same business every call, so tests can recompute the truth
    days = pd.date_range("2024-01-01", "2025-06-30")
    shops = ["SH-A", "SH-B", "SH-C"]
    orders = pd.DataFrame({"order_id": [f"OR{i:05d}" for i in range(n)], "order_date": r.choice(days, n), "store_id": r.choice(shops, n),
                           "customer_id": [f"CU{x:04d}" for x in r.integers(1, 400, n)],
                           "status": r.choice(["Delivered", "Delivered", "Delivered", "Cancelled", "Returned"], n), "order_total": np.round(r.uniform(100, 5000, n), 2)})
    od = pd.to_datetime(orders["order_date"])
    orders["ship_date"] = od + pd.to_timedelta(r.integers(0, 2, n), "D")                       # always well before the promise
    orders["promised_date"] = od + pd.to_timedelta(5, "D")
    orders["delivery_date"] = od + pd.to_timedelta(r.integers(2, 9, n), "D")                   # some arrive after the promise
    lines = pd.DataFrame({"line_id": [f"L{i:06d}" for i in range(2 * n)], "order_id": np.repeat(orders["order_id"].to_numpy(), 2),
                          "sku": r.choice([f"SK-{i:03d}" for i in range(40)], 2 * n), "quantity": r.integers(1, 4, 2 * n),
                          "discount_pct": r.choice([0, 0, 1, 2, 5, 10], 2 * n).astype(float), "line_total": np.round(r.uniform(50, 2500, 2 * n), 2)})
    returns = pd.DataFrame({"return_id": [f"RT{i:05d}" for i in range(300)], "order_id": r.choice(orders["order_id"], 300), "return_date": r.choice(days, 300),
                            "qty_returned": r.integers(1, 3, 300), "refund_amount": np.round(r.uniform(50, 900, 300), 2)})
    stores = pd.DataFrame({"store_id": shops, "store_name": ["North shop", "South shop", "East shop"], "region": ["North", "South", "East"],
                           "opened": pd.to_datetime(["2019-01-01", "2020-05-01", "2023-03-01"])})
    traffic = pd.DataFrame([(d, s) for d in days for s in ["Search", "Social", "Email"]], columns=["date", "source"])
    m = len(traffic)
    traffic = traffic.assign(sessions=r.integers(100, 900, m), bounce_rate=np.round(r.uniform(0.2, 0.6, m), 3), avg_session_sec=r.integers(60, 240, m),
                             add_to_cart=r.integers(5, 40, m), orders=r.integers(1, 15, m), mobile_share=np.round(r.uniform(0.5, 0.8, m), 3))
    staff = pd.DataFrame({"employee_id": [f"E{i:02d}" for i in range(12)], "store_id": r.choice(shops, 12), "join_date": r.choice(days, 12),
                          "monthly_salary_inr": r.integers(18000, 70000, 12)})
    expenses = pd.DataFrame([(mo, s, c) for mo in pd.period_range("2024-01", "2025-06", freq="M").astype(str) for s in shops for c in ["Rent", "Power", "Wages"]],
                            columns=["month", "store_id", "expense_category"])
    expenses["amount_inr"] = r.integers(20000, 90000, len(expenses))
    expenses["budget_inr"] = expenses["amount_inr"] + r.integers(-5000, 5000, len(expenses))
    about = pd.DataFrame({"Demo business data for a test. Every name and number here is made up and means nothing at all.": ["Sheets: orders, lines", "Version 1"]})
    return {"About": about, "Orders": orders, "Order_Lines": lines, "Returns": returns, "Stores": stores, "Web_Traffic": traffic, "Staff": staff,
            "Expenses_vs_Budget": expenses}


def _run(tmp: str):
    p = Path(tmp) / "business.xlsx"
    _book(p, _business())
    files = [{"id": 1, "name": "business.xlsx", "path": str(p)}]
    return p, pipeline.analyze("wb", files, {}, tmp, None)


def test_every_table_sheet_is_read_and_notes_sheets_are_skipped():
    tmp = tempfile.mkdtemp()
    p, rep = _run(tmp)
    names = [n for n, _ in table_sheets(str(p))]
    assert "About" not in names and {"Orders", "Order_Lines", "Returns", "Stores", "Web_Traffic", "Staff", "Expenses_vs_Budget"} <= set(names)
    read = {f["name"].split(" › ")[-1]: f for f in rep["reading"]["files"]}
    assert set(read) == set(names)
    links = {(l["child"].split(" › ")[-1], l["child_col"], l["parent"].split(" › ")[-1]) for l in rep["reading"]["links"] if l["use"]}
    assert ("Order_Lines", "order_id", "Orders") in links
    assert ("Orders", "store_id", "Stores") in links                  # a list of 3 stores still links through store_id
    assert read["Stores"]["role"] == "master" and read["Stores"]["time_col"] is None      # 'opened' describes a store, it is not an event
    assert read["Staff"]["role"] == "master"
    assert read["Returns"]["time_col"] == "return_date"              # 'return_date' is the timeline of a returns table


def test_header_rules_units_shares_money_and_record_ids():
    tmp = tempfile.mkdtemp()
    _, rep = _run(tmp)
    cols = {(f["name"].split(" › ")[-1], c["name"]): c for f in rep["reading"]["files"] for c in f["columns"]}
    assert cols[("Web_Traffic", "bounce_rate")]["concept"] == "percent"
    assert cols[("Web_Traffic", "mobile_share")]["concept"] == "percent"               # a share, not a phone number
    assert cols[("Web_Traffic", "avg_session_sec")]["concept"] == "duration"
    assert cols[("Web_Traffic", "add_to_cart")]["concept"] == "activity_count"
    assert cols[("Web_Traffic", "orders")]["concept"] == "activity_count"
    assert cols[("Staff", "monthly_salary_inr")]["type"] == "measure"                  # money, never an Excel date
    assert cols[("Returns", "refund_amount")]["concept"] == "refund"                   # refunds are not sales
    assert cols[("Returns", "qty_returned")]["concept"] == "units_returned"
    assert cols[("Returns", "return_id")]["concept"] != "order_id"
    assert cols[("Expenses_vs_Budget", "amount_inr")]["concept"] == "expense"          # an amount in an expenses table is money spent
    assert cols[("Expenses_vs_Budget", "expense_category")]["concept"] == "group"


def test_grids_count_no_rows_on_time_uses_delivery_and_currency_is_shared():
    tmp = tempfile.mkdtemp()
    _, rep = _run(tmp)
    parts = rep["overview"].get("parts") or [{"overview": rep["overview"]}]
    tiles = {(t["metric"], t.get("source", "").split(" › ")[-1]): t for p in parts for t in p["overview"]["tiles"]}
    web = [t for (m, src), t in tiles.items() if src == "Web_Traffic"]
    assert web and not any(t["metric"] == "transactions" for t in web)              # a date x source grid has no 'transactions'
    sec = [t for t in web if t["metric"] == "avg_duration"]
    assert sec and sec[0]["unit"] == "sec"
    od = _business()["Orders"]
    ok = ~od["status"].isin(["Cancelled", "Returned"])
    d = od[ok & od["delivery_date"].notna()]
    want = float((pd.to_datetime(d["delivery_date"]) <= pd.to_datetime(d["promised_date"])).mean())
    ot = [t for (m, _), t in tiles.items() if m == "on_time_rate"]
    assert ot and abs(ot[0]["value"] - want) < 0.02 and ot[0]["value"] < 0.95      # judged on delivery, not on the earlier ship date


def test_returns_count_even_when_their_order_was_returned():
    tmp = tempfile.mkdtemp()
    _, rep = _run(tmp)
    parts = rep["overview"].get("parts") or [{"overview": rep["overview"]}]
    refund = [t for p in parts for t in p["overview"]["tiles"] if "refund" in t["metric"]]
    assert refund and abs(refund[0]["value"] - _business()["Returns"]["refund_amount"].sum()) < 0.01


def test_percent_written_as_whole_numbers_with_ones_is_not_mixed():
    df = pd.DataFrame({"order_id": [f"O{i}" for i in range(400)], "order_date": pd.date_range("2024-01-01", periods=400).strftime("%Y-%m-%d"),
                       "line_total": R.uniform(10, 100, 400).round(2), "discount_pct": R.choice([0.0, 1.0, 2.0, 5.0, 10.0], 400)})
    tmp = tempfile.mkdtemp(); p = Path(tmp) / "s.csv"; df.to_csv(p, index=False)
    rep = pipeline.analyze("pc", [{"id": 1, "name": "s.csv", "path": str(p)}], {}, tmp, None)
    checks = [c for f in rep["data_check"]["files"] for c in f["checks"] if c["id"] == "mixed_scales"]
    assert checks and all(c["status"] in ("pass", "n/a") for c in checks)          # 1 means 1%, as the other values do


def test_snapshot_on_order_and_stock_value_are_levels():
    days = pd.date_range("2024-01-07", periods=40, freq="W")
    rows = [(d, s, k) for d in days for s in ["W1", "W2"] for k in [f"P{i:02d}" for i in range(30)]]
    df = pd.DataFrame(rows, columns=["snapshot_date", "store_id", "sku"])
    n = len(df)
    base = R.integers(5, 60, n)
    df["qty_on_hand"] = base
    df["qty_on_order"] = R.integers(0, 30, n)
    df["unit_cost"] = 100.0
    df["stock_value"] = df["qty_on_hand"] * df["unit_cost"]
    p = prepare(df.assign(_row=np.arange(n) + 2), "inventory")
    m = infer_table(p)
    c = {k: v["concept"] for k, v in m["columns"].items()}
    assert c["qty_on_hand"] == "stock_level" and c["qty_on_order"] == "on_order" and c["stock_value"] == "stock_value"

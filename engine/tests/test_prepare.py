import numpy as np
import pandas as pd
from alpha_engine.understand.prepare import prepare


def base(n=600):
    rng = np.random.default_rng(3)
    d = pd.DataFrame({
        "order_id": [f"ORD-{i:06d}" for i in range(n)],
        "order_date": pd.date_range("2025-01-01", periods=n // 3, freq="D").repeat(3).strftime("%Y-%m-%d"),
        "order_status": rng.choice(["Completed", "Cancelled", "Returned", "Pending"], n, p=[.8, .06, .07, .07]),
        "payment_status": rng.choice(["Paid", "Failed"], n, p=[.9, .1]),
        "currency": rng.choice(["USD", "EUR", "GBP"], n, p=[.6, .3, .1]),
        "city": rng.choice(["Pune", "Delhi", "Goa"], n),
        "quantity": rng.integers(1, 5, n),
        "net_sales": rng.normal(100, 10, n).round(2),
        "customer_rating": rng.choice([3.5, 4.0, 4.5], n),
    })
    d["_row"] = d.index + 2
    return d


def test_events_file_with_time_money_currency_and_exclusions():
    p = prepare(base())
    assert p.kind == "events" and p.time_col == "order_date"
    assert p.money_col == "net_sales"
    names = [m.name for m in p.measures]
    assert "net_sales [USD]" in names and "net_sales [EUR]" in names     # never added across currencies
    assert "net_sales" not in names
    assert "rows" in names and "customer_rating" in names
    assert any(n.startswith("rate of order_status = Cancelled") for n in names)
    assert not p.ok.all() and p.ok.mean() < 0.9                             # cancelled/returned left out of money
    assert "city" in p.slices and "currency" in p.slices
    assert any("currencies" in n for n in p.notes)


def test_only_order_status_decides_exclusion_but_inconsistency_is_reported():
    p = prepare(base())
    d = p.df
    assert (p.ok == ~d["order_status"].isin(["Cancelled", "Returned"])).all()
    assert any("payment_status" in w for w in p.warnings)


def test_total_rows_are_dropped():
    d = base(210)
    tot = d.iloc[[0]].copy(); tot["order_id"] = "Grand Total"; tot["order_date"] = None
    d = pd.concat([d, tot], ignore_index=True)
    p = prepare(d)
    assert len(p.df) == 210 and any("total" in n.lower() for n in p.notes)


def test_summary_file_is_not_analysed():
    d = pd.DataFrame({"Total Transactions": [138116], "Total Revenue": ["$177,134,263.74"], "Date Range": ["2021-01-01 to 2025-12-31"]})
    d["_row"] = [2]
    p = prepare(d)
    assert p.kind == "summary" and p.measures == []


def test_reference_file_without_dates():
    d = pd.DataFrame({"customer_id": [f"C{i:05d}" for i in range(300)], "segment": ["A", "B", "C"] * 100, "age": np.arange(300) % 60 + 18})
    d["_row"] = d.index + 2
    p = prepare(d)
    assert p.kind == "reference" and p.time_col is None


def test_date_built_from_year_and_month_columns():
    d = pd.DataFrame({"year": [2024] * 12 + [2025] * 12, "month": list(range(1, 13)) * 2, "sales": np.arange(24) * 10.0 + 100})
    d["_row"] = d.index + 2
    p = prepare(d)
    assert p.time_col == "year+month" and p.df["_t"].notna().all()


def test_row_order_time_only_with_owner_confirmation():
    d = pd.DataFrame({"sales": np.arange(400) * 1.0, "grp": ["a", "b"] * 200}); d["_row"] = d.index + 2
    assert prepare(d).time_col is None
    p = prepare(d, confirmed={"__rows_in_time_order__": True})
    assert p.synthetic_time and any("row order" in w for w in p.warnings)


def test_ambiguous_dates_are_reported():
    d = pd.DataFrame({"sale_date": ["04/05/2026", "03/06/2026", "01/02/2026"] * 60, "amount": np.arange(180) * 1.0}); d["_row"] = d.index + 2
    assert any("day-first" in w for w in prepare(d).warnings)

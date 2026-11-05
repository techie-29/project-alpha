"""The upgraded metric catalogue: every new metric checked against a hand calculation on generated data."""
import numpy as np
import pandas as pd
from alpha_engine.understand.prepare import prepare
from alpha_engine.model.build import build_model
from alpha_engine.metrics.frame import build_frame
from alpha_engine.metrics.catalogue import available, value, by_group, BY_ID, CATALOGUE

R = np.random.default_rng(7)


def _frame(df, name):
    df = df.copy(); df.insert(0, "_row", range(2, len(df) + 2))
    p = prepare(df, name)
    m = build_model({name: p}, [])
    fm = m["files"][name]
    return build_frame(p, fm["columns"], fm["file"], {name: p}, [], m["files"])


def _sales(n=3000):
    d = pd.date_range("2022-01-01", "2023-12-31 20:00", periods=n)
    q = R.integers(1, 6, n); pr = R.choice([50.0, 120.0, 300.0], n); disc = R.choice([0.0, 0.0, 0.1, 0.2], n)
    sales = np.round(q * pr * (1 - disc), 2)
    profit = np.round(sales * np.where(disc > 0, R.uniform(-0.3, 0.1, n), R.uniform(0.05, 0.35, n)), 2)
    cust = R.integers(1, 300, n)
    df = pd.DataFrame({"Order ID": [f"O{i:05d}" for i in range(n)], "Order Date": d.strftime("%Y-%m-%d %H:%M"), "Customer ID": [f"C{x:03d}" for x in cust],
                       "Product ID": [f"P{x:02d}" for x in R.integers(1, 40, n)], "Store": R.choice(["S1", "S2", "S3"], n), "Quantity": q, "Unit Price": pr,
                       "Discount": disc, "Sales": sales, "Profit": profit, "Shipping Cost": np.round(R.uniform(5, 30, n), 2)})
    return df


def test_core_count_and_tiers():
    core = [m for m in CATALOGUE if m.tier == "core"]
    assert 45 <= len(core) <= 55
    assert all(m.headline == 0 for m in CATALOGUE if m.tier == "input")


def test_new_sales_profit_customer_product_metrics_match_hand_calculation():
    df = _sales()
    F = _frame(df, "sales.csv")
    ids = {m.id for m in available(F)}
    for mid in ("sales_growth", "biggest_order_share", "expenses_share", "profit_per_order", "loss_line_share", "loss_amount", "discount_margin_gap",
                "repeat_rate", "new_customers", "quiet_customers", "top_customer_share", "top_product_share", "products_losing", "slow_movers", "revenue_per_site"):
        assert mid in ids, mid
    v = lambda mid: value(F, BY_ID[mid])
    s, p = df["Sales"], df["Profit"]
    assert abs(v("loss_line_share") - (p < 0).mean()) < 1e-9
    assert abs(v("loss_amount") - (-p[p < 0].sum())) < 1e-6
    disc = df["Discount"] > 0
    gap = p[disc].sum() / s[disc].sum() - p[~disc].sum() / s[~disc].sum()
    assert abs(v("discount_margin_gap") - gap) < 1e-9
    assert abs(v("expenses_share") - df["Shipping Cost"].sum() / s.sum()) < 1e-9
    assert abs(v("biggest_order_share") - s.max() / s.sum()) < 1e-9
    per = df.groupby("Customer ID")["Order ID"].nunique()
    assert abs(v("repeat_rate") - (per >= 2).mean()) < 1e-9
    assert v("new_customers") == df["Customer ID"].nunique()             # over the whole period every customer is new once
    m = df.assign(_m=pd.to_datetime(df["Order Date"]).dt.to_period("M")).groupby("_m")["Sales"].sum()
    assert abs(v("sales_growth") - (m.iloc[-12:].sum() - m.iloc[-24:-12].sum()) / m.iloc[-24:-12].sum()) < 1e-9
    r = df.groupby("Customer ID")["Sales"].sum().sort_values(ascending=False)
    assert abs(v("top_customer_share") - r.iloc[:int(np.ceil(0.1 * len(r)))].sum() / r.sum()) < 1e-9
    g = df.groupby("Product ID")["Profit"].sum()
    assert v("products_losing") == int((g < 0).sum())
    rows = by_group(F, BY_ID["loss_line_share"], "Store")
    assert {x["group"] for x in rows} == {"S1", "S2", "S3"}
    s1 = df[df["Store"] == "S1"]["Profit"]
    assert abs(next(x["value"] for x in rows if x["group"] == "S1") - (s1 < 0).mean()) < 1e-9


def test_quiet_customers_found():
    rows = []
    for c in range(40):                                    # regular weekly buyers
        last = 52 if c >= 10 else 20                       # 10 of them stopped after week 20
        rows += [(f"2024-01-01", f"C{c}", w) for w in range(last)]
    df = pd.DataFrame([(pd.Timestamp(a) + pd.Timedelta(weeks=w), c, 100.0) for a, c, w in rows], columns=["Order Date", "Customer ID", "Sales"])
    df["Order ID"] = [f"O{i}" for i in range(len(df))]
    F = _frame(df, "orders.csv")
    assert value(F, BY_ID["quiet_customers"]) == 10


def test_stock_cover_dead_and_overstock():
    dates = pd.date_range("2024-01-01", periods=120)
    rows, expect_dead, expect_over = [], 0.0, 0.0
    for i in range(30):
        kind = "dead" if i < 5 else ("over" if i < 10 else "moving")
        stock = int(R.integers(80, 120)) if kind != "over" else 600
        cost = float(R.choice([5.0, 10.0, 20.0]))
        for d in dates:
            sold = 0 if kind == "dead" else (int(R.random() < 0.5) if kind == "over" else int(R.poisson(4)))
            stock = max(0, stock - sold)
            if kind == "moving" and stock < 15:
                stock += 100                                           # restocked
            rows.append((d.strftime("%Y-%m-%d"), f"SKU{i:02d}", stock, sold, cost))
        if kind == "dead":
            expect_dead += stock * cost
    df = pd.DataFrame(rows, columns=["Date", "SKU", "Stock On Hand", "Units Sold", "Unit Cost"])
    last90 = df[pd.to_datetime(df["Date"]) > pd.to_datetime(df["Date"]).max() - pd.Timedelta(days=90)]
    rate = last90.groupby("SKU")["Units Sold"].sum() / 90
    end = df[df["Date"] == df["Date"].max()].set_index("SKU")
    cover = end["Stock On Hand"] / rate.where(rate > 0)
    expect_over = float((end["Stock On Hand"] * end["Unit Cost"])[cover > 180].sum())
    F = _frame(df, "inventory.csv")
    assert F.role == "snapshot" and F.canon.get("stock_level") == "Stock On Hand" and F.canon.get("quantity") == "Units Sold"
    assert abs(value(F, BY_ID["dead_stock_value"]) - expect_dead) < 1e-6
    assert abs(value(F, BY_ID["overstock_value"]) - expect_over) < 1e-6 and expect_over > 0
    assert value(F, BY_ID["avg_cover"]) is not None

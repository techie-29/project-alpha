"""Synthetic businesses with known truth, used to measure what the scan finds and what it wrongly reports."""
import numpy as np
import pandas as pd


def business(seed=0, years=2.0, planted=True, seasonal=True, drift=False):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2024-01-01", periods=int(365 * years), freq="D")
    cities = ["Pune", "Delhi", "Goa", "Surat", "Kochi"]
    prods = {"Laptop X": ("Laptops", 900), "Phone A": ("Phones", 500), "TV S": ("TVs", 700), "Cable": ("Accessories", 15), "Mouse": ("Accessories", 25)}
    rows = []
    for d in days:
        season = 1 + (0.35 if (seasonal and d.month in (11, 12)) else 0) + (0.0003 * (d - days[0]).days if drift else 0)
        n = rng.poisson(30 * season)
        for _ in range(n):
            rows.append((d, rng.choice(cities), rng.choice(list(prods)), rng.integers(1, 4)))
    df = pd.DataFrame(rows, columns=["order_date", "city", "product", "quantity"])
    df["category"] = df["product"].map(lambda p: prods[p][0])
    df["unit_price"] = df["product"].map(lambda p: prods[p][1])
    df["status"] = "Completed"
    if planted:
        w = (df.order_date >= "2024-09-02") & (df.order_date < "2024-09-30") & (df["product"] == "Laptop X")
        df = df[~(w & (rng.random(len(df)) < 0.6))]                       # Laptop X sales collapse for 4 weeks
        late = (df.order_date >= "2024-12-01") & (df.city == "Pune")
        df.loc[late & (rng.random(len(df)) < 0.18), "status"] = "Returned"  # Pune returns rise from Dec
    base_ret = (rng.random(len(df)) < 0.05) & (df.status == "Completed")
    df.loc[base_ret, "status"] = "Returned"
    df["net_sales"] = (df.quantity * df.unit_price * rng.normal(1, 0.05, len(df))).round(2)
    df["order_id"] = [f"ORD-{i:07d}" for i in range(len(df))]
    df["order_date"] = df.order_date.dt.strftime("%Y-%m-%d")
    df["_row"] = np.arange(len(df)) + 2
    return df.reset_index(drop=True)

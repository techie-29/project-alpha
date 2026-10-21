"""A synthetic multi-file business with known, planted patterns:
- region West: returns about 3x more often than the rest
- deliveries later than promised get lower ratings
- channel Store declines steadily; Online grows
- campaign SALE10 orders have a much lower margin
- 5 products are out of stock at the end; 8 products have stock but never sell (dead stock)
- top 10% of customers bring a large share of revenue (heavy-tailed spend)"""
import numpy as np
import pandas as pd


def make(seed=7, days=730, n_customers=1500, n_products=60):
    r = np.random.default_rng(seed)
    start = pd.Timestamp("2023-01-02")
    products = pd.DataFrame({"product_id": [f"P{i:04d}" for i in range(n_products)], "product_name": [f"Product {i}" for i in range(n_products)],
                             "category": r.choice(["Kitchen", "Garden", "Toys", "Books"], n_products),
                             "unit_cost": np.round(r.uniform(3, 60, n_products), 2)})
    products["list_price"] = np.round(products["unit_cost"] * r.uniform(1.4, 2.2, n_products), 2)
    dead = products["product_id"].iloc[-8:].tolist()
    sellable = products[~products["product_id"].isin(dead)]
    cust = pd.DataFrame({"customer_id": [f"C{i:05d}" for i in range(n_customers)], "segment": r.choice(["Retail", "Business", "VIP"], n_customers, p=[.7, .25, .05]),
                         "region": r.choice(["North", "South", "East", "West"], n_customers)})
    weight = r.pareto(1.3, n_customers) + 0.05
    rows, lines = [], []
    oid = 0
    for d in range(days):
        day = start + pd.Timedelta(days=d)
        n = r.poisson(70)
        for _ in range(n):
            oid += 1
            ci = r.choice(n_customers, p=weight / weight.sum())
            frac = d / days
            ch = r.choice(["Online", "Store", "Marketplace"], p=[0.35 + 0.3 * frac, 0.45 - 0.3 * frac, 0.20])
            camp = r.choice(["", "SALE10", "WELCOME"], p=[0.8, 0.1, 0.1])
            promised = int(r.choice([2, 3, 5]))
            late = r.random() < 0.18
            actual = promised + (int(r.integers(1, 6)) if late else -int(r.integers(0, 2)))
            rating = float(np.clip(np.round(r.normal(4.3 - (1.2 if late else 0), 0.5), 1), 1, 5))
            reg = cust.region.iloc[ci]
            status = "Returned" if r.random() < (0.12 if reg == "West" else 0.04) else ("Cancelled" if r.random() < 0.03 else "Completed")
            amount = 0.0; cost = 0.0
            for _l in range(int(r.integers(1, 4))):
                pi = r.integers(len(sellable))
                pr = sellable.iloc[pi]
                q = int(r.integers(1, 4))
                price = pr.list_price * (0.75 if camp == "SALE10" else 1.0)
                lines.append((f"O{oid:07d}", pr.product_id, q, round(price, 2), round(q * price, 2)))
                amount += q * price; cost += q * pr.unit_cost
            rows.append((f"O{oid:07d}", day, cust.customer_id.iloc[ci], ch, camp or None, status, promised, max(actual, 0), rating, round(amount, 2), round(cost, 2)))
    orders = pd.DataFrame(rows, columns=["order_id", "order_date", "customer_id", "channel", "campaign", "status", "promised_days", "delivery_days", "rating", "order_total", "order_cost"])
    items = pd.DataFrame(lines, columns=["order_id", "product_id", "qty", "unit_price", "line_amount"])
    # weekly stock snapshot
    weeks = pd.date_range(start, start + pd.Timedelta(days=days - 1), freq="7D")
    out_of_stock = products["product_id"].iloc[:5].tolist()
    snap = []
    for wi, w in enumerate(weeks):
        for pid in products["product_id"]:
            if pid in out_of_stock and wi >= len(weeks) - 3:
                lvl = 0
            elif pid in dead:
                lvl = 40
            else:
                lvl = int(r.integers(10, 200))
            snap.append((w, pid, lvl))
    stock = pd.DataFrame(snap, columns=["snapshot_date", "product_id", "on_hand"])
    return {"orders.csv": orders, "order_items.csv": items, "products.csv": products, "customers.csv": cust, "stock.csv": stock}, {"dead": dead, "out_of_stock": out_of_stock}

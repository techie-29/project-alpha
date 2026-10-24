"""Test fixture: a messy inventory business (Indian distributor) with planted patterns and many date formats.
make(out_dir) writes 5 files and returns the true numbers."""
import numpy as np, pandas as pd, random, json
from openpyxl import Workbook


def make(OUT):
    rng = np.random.default_rng(7); random.seed(7)
    START, END = pd.Timestamp("2023-04-01"), pd.Timestamp("2025-03-31")
    cats = {"Dairy": (40, 70, 20), "Snacks": (15, 30, 180), "Beverages": (25, 45, 365), "Personal Care": (60, 140, 730), "Household": (80, 160, 900)}
    sups = ["FastSupply", "Prime Traders", "Om Distributors", "Shree Agencies"]
    items = []
    for i in range(1, 61):
        cat = list(cats)[i % 5]
        lo, hi, life = cats[cat]
        cost = round(float(rng.uniform(lo, hi)), 2)
        items.append(dict(code=f"SKU-{i:04d}", name=f"{cat} item {i}", cat=cat, sup=sups[i % 4], cost=cost,
                          price=round(cost * float(rng.uniform(1.15, 1.45)), 2), reorder=int(rng.integers(20, 60)), life=life,
                          pop=float(rng.gamma(2.0, 1.0)), added=START - pd.Timedelta(days=int(rng.integers(30, 700)))))
    dead = {"SKU-0013", "SKU-0027", "SKU-0041"}          # stopped selling after Sep 2024
    outs = {"SKU-0005", "SKU-0018", "SKU-0032", "SKU-0046"}  # run out at the end
    wb = Workbook(); ws = wb.active; ws.title = "Items"
    ws.append(["Item Master - Shree Distributors"]); ws.append([])
    ws.append(["Item Code", "Item Name", "Category", "Supplier", "Unit Cost", "MRP", "Reorder Level", "Added On", "Batch Expiry"])
    exp_soon = set()
    for k, it in enumerate(items):
        if it["cat"] == "Dairy" and k % 2 == 0:
            exp = END + pd.Timedelta(days=int(rng.integers(3, 25))); exp_soon.add(it["code"])
        else:
            exp = END + pd.Timedelta(days=int(rng.integers(60, it["life"] + 900)))
        added = it["added"].to_pydatetime() if k % 3 else it["added"].strftime("%d-%b-%y")      # real Excel dates mixed with text
        ws.append([it["code"], it["name"], it["cat"], it["sup"], f"₹{it['cost']:,.2f}", it["price"], it["reorder"], added,
                   exp.strftime("%d/%m/%Y") if k % 4 else exp.strftime("%Y-%m-%d")])
    wb.save(f"{OUT}/Item Master.xlsx")

    # movements
    days = pd.date_range(START, END, freq="D")
    rows, stock = [], {it["code"]: 300 for it in items}
    closing = {}
    season = lambda d: 1.0 + 0.6 * (d.month in (10, 11)) + 0.15 * (d - START).days / 730
    fmt_pool = ["%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y", "%d.%m.%Y %H:%M", "serial", "%d/%m/%Y"]
    def fmt(d):
        f = random.choice(fmt_pool)
        if f == "serial":
            return str((d - pd.Timestamp("1899-12-30")).days)
        return (d + pd.Timedelta(minutes=random.randint(540, 1260))).strftime(f)
    ref = 100000
    for d in days:
        for it in items:
            c = it["code"]
            lam = it["pop"] * 1.2 * season(d)
            if c in dead and d > pd.Timestamp("2024-09-30"): lam = 0
            q = int(rng.poisson(lam))
            if c in outs and d > pd.Timestamp("2025-02-15"):
                q = min(q + 3, stock[c])
            q = min(q, stock[c])
            wh = "WH-Pune" if rng.random() < 0.4 else "WH-Mumbai"
            if q > 0:
                ref += 1; stock[c] -= q
                rows.append([fmt(d), c, "Sale" if rng.random() < 0.97 else "OUT", q, wh, f"REF{ref}"])
            if rng.random() < (0.004 if wh == "WH-Mumbai" else 0.012):
                dq = int(rng.integers(1, 5)); dq = min(dq, stock[c])
                if dq: ref += 1; stock[c] -= dq; rows.append([fmt(d), c, "Damaged", dq, wh, f"REF{ref}"])
            if stock[c] < it["reorder"] and not (c in outs and d > pd.Timestamp("2025-01-31")) and not (c in dead and d > pd.Timestamp("2024-09-30")) and d.weekday() == 0:
                add = 200; ref += 1; stock[c] += add
                rows.append([fmt(d), c, "IN", add, "WH-Mumbai", f"REF{ref}"])
        if d.is_month_end:
            closing[d.strftime("%b-%Y")] = dict(stock)
    mv = pd.DataFrame(rows, columns=["Txn Dt", "Item Code", "Movement", "Qty", "Warehouse", "Ref No"])
    mv.loc[mv.sample(40, random_state=1).index, "Txn Dt"] = ""
    mv.loc[mv.sample(15, random_state=2).index, "Txn Dt"] = "N/A"
    mv.to_csv(f"{OUT}/stock_movements.csv", index=False)

    # wide monthly closing stock
    wb = Workbook(); ws = wb.active; ws.title = "Closing"
    ws.append(["Item Code", "Item Name"] + list(closing))
    for it in items:
        ws.append([it["code"], it["name"]] + [closing[m][it["code"]] for m in closing])
    wb.save(f"{OUT}/monthly_closing_stock.xlsx")

    # purchase orders: late supplier
    po = []
    for n, d in enumerate(pd.date_range(START, END - pd.Timedelta(days=20), freq="3D")):
        it = items[n % 60]
        exp_d = d + pd.Timedelta(days=7)
        late = int(rng.integers(4, 12)) if it["sup"] == "FastSupply" else int(rng.integers(-1, 3))
        rec = exp_d + pd.Timedelta(days=late)
        qo = int(rng.integers(100, 300)); qr = qo if rng.random() > 0.1 else qo - int(rng.integers(5, 40))
        po.append([f"PO/{n + 1:05d}", it["code"], it["sup"], d.strftime("%Y%m%d"), exp_d.strftime("%Y/%m/%d"),
                   (rec + pd.Timedelta(hours=10, minutes=15)).strftime("%Y-%m-%dT%H:%M:%S+05:30") if n % 17 else "", qo, qr if n % 17 else "", it["cost"]])
    pd.DataFrame(po, columns=["PO Number", "Item Code", "Supplier", "Order Date", "Expected Date", "Received Date", "Qty Ordered", "Qty Received", "Rate"]).to_csv(f"{OUT}/purchase_orders.csv", index=False)

    # daily sales summary in US format
    truth = {"stock_value_latest": round(sum(stock[it["code"]] * it["cost"] for it in items), 2),
             "units_on_hand": int(sum(stock.values())), "zero_stock": sorted(c for c in stock if stock[c] == 0),
             "expiring_soon": sorted(exp_soon), "dead": sorted(dead), "outs": sorted(outs),
             "units_sold": int(mv[mv.Movement.isin(["Sale", "OUT"])].Qty.sum()), "damaged_units": int(mv[mv.Movement == "Damaged"].Qty.sum())}
    rng2 = np.random.default_rng(3)
    d = pd.date_range("2023-04-01", "2025-03-31")
    pd.DataFrame({"Day": d.strftime("%m/%d/%Y"), "Bills": rng2.poisson(120, len(d)), "Cash Sales": np.round(rng2.normal(52000, 6000, len(d)), 2),
                  "Card Sales": np.round(rng2.normal(31000, 5000, len(d)), 2)}).to_csv(f"{OUT}/counter_daily_summary.csv", index=False)
    return truth

"""Builds the three sample businesses shown on the Upload page (frontend/public/samples).

Each one is realistic, slightly messy (so mapping and cleaning have work to do), and has a few planted
stories for Alpha to find. Deterministic: the same files every run.  Run:  python scripts/make_samples.py
"""
import json
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "samples")
START, END = date(2025, 1, 1), date(2026, 10, 31)
DAYS = [START + timedelta(d) for d in range((END - START).days + 1)]


def _mess(df, rng, text_cols=(), num_col=None, blank_cols=(), dup=5):
    """A little real-world mess: odd casing, blanks, a letter O typed for a zero, repeated rows."""
    df = df.copy()
    for c in text_cols:
        idx = rng.choice(len(df), size=max(3, len(df) // 400), replace=False)
        df.loc[idx, c] = df.loc[idx, c].astype(str).str.lower()
    for c in blank_cols:
        idx = rng.choice(len(df), size=max(3, len(df) // 300), replace=False)
        df.loc[idx, c] = None
    if num_col:
        df[num_col] = df[num_col].astype(object)
        for i in rng.choice(len(df), size=3, replace=False):
            v = str(df.at[i, num_col])
            if "0" in v:
                df.at[i, num_col] = v.replace("0", "O", 1)
    if dup:
        df = pd.concat([df, df.sample(dup, random_state=1)], ignore_index=True)
    return df


def _season(d, peaks):
    return peaks.get(d.month, 1.0) * (1 + 0.0007 * (d - START).days)        # gentle growth over time


def build(spec):
    rng = np.random.default_rng(spec["seed"])
    prods = pd.DataFrame(spec["products"], columns=["product_id", "product_name", "category", "supplier", "unit_cost", "list_price"])
    n_cust = spec["customers"]
    cust = pd.DataFrame({
        "customer_id": [f"{spec['prefix']}C{i:04d}" for i in range(n_cust)],
        "customer_name": [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(n_cust)],
        "gender": rng.choice(["F", "M"], n_cust, p=spec.get("gender_p", [0.5, 0.5])),
        "city": rng.choice(spec["cities"], n_cust),
        "member_since": [str(START - timedelta(int(x))) for x in rng.integers(0, 700, n_cust)],
    })
    loyal = rng.random(n_cust) ** 2.2                                       # a few customers buy far more often
    loyal = loyal / loyal.sum()
    orders, items = [], []
    oid = 0
    pw = np.array(spec["popularity"], dtype=float)
    for d in DAYS:
        base = spec["per_day"] * _season(d, spec["peaks"]) * spec["weekday"][d.weekday()]
        for _ in range(rng.poisson(base)):
            oid += 1
            o = {"order_id": f"{spec['prefix']}{oid:06d}", "order_date": d.isoformat(),
                 "customer_id": cust.customer_id[rng.choice(n_cust, p=loyal)] if rng.random() > spec.get("walk_in", 0) else ""}
            for col, vals, p in spec["order_cols"]:
                o[col] = rng.choice(vals, p=p)
            for v, pr in spec.get("background", []):            # every group has a little of each problem
                if o["status"] == spec["order_cols"][-1][1][0] and rng.random() < pr: o["status"] = v
            spec["tweak"](o, d, rng)
            k = min(len(prods), 1 + rng.poisson(spec["items_per_order"] - 1))
            total = cost = 0.0
            for pi in rng.choice(len(prods), size=k, replace=False, p=pw / pw.sum()):
                p = prods.iloc[pi]
                qty = int(1 + rng.poisson(spec.get("qty", 0.4)))
                price = round(p.list_price * rng.uniform(0.97, 1.03), 2)
                disc = spec["discount"](o)
                line = round(qty * price * (1 - disc), 2)
                items.append({"order_id": o["order_id"], "product_id": p.product_id, "qty": qty, "unit_price": price, "line_amount": line})
                total += line
                cost += qty * p.unit_cost
            o["order_total"], o["order_cost"] = round(total, 2), round(cost, 2)
            orders.append(o)
    orders, items = pd.DataFrame(orders), pd.DataFrame(items)

    # stock: weekly snapshots; a few best sellers run dry near the end, a few slow lines sit untouched
    snaps = []
    weeks = pd.date_range(START, END, freq="W-MON")
    for _, p in prods.iterrows():
        level = int(rng.integers(40, 160))
        for w in weeks:
            level = max(0, level + int(rng.integers(-25, 30)))
            snaps.append({"snapshot_date": w.date().isoformat(), "product_id": p.product_id, "on_hand": level})
    stock = pd.DataFrame(snaps)
    last = stock.snapshot_date == stock.snapshot_date.max()
    top = items.groupby("product_id").line_amount.sum().sort_values(ascending=False).index
    stock.loc[last & stock.product_id.isin(top[:3]), "on_hand"] = 0
    dead = spec.get("dead", [])
    if dead:                                                               # never sold: drop their sales lines
        items = items[~items.product_id.isin(dead)]
    out = {
        "orders": _mess(orders, rng, text_cols=[spec["order_cols"][0][0]], num_col="order_total", blank_cols=["customer_id"]),
        "order_items": items.reset_index(drop=True),
        "products": prods,
        "customers": _mess(cust, rng, text_cols=["city"], blank_cols=["gender"], dup=0),
        "stock": stock,
    }
    if not spec.get("stock", True):
        del out["stock"]
    return out


FIRST = ["Aarav", "Priya", "Rahul", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya", "Rohan", "Isha", "Imran", "Fatima", "Karthik", "Meera", "Sameer", "Divya", "Aditya", "Nisha", "Farhan", "Pooja"]
LAST = ["Sharma", "Iyer", "Khan", "Reddy", "Patel", "Nair", "Gupta", "Rao", "Singh", "Shaikh", "Menon", "Das", "Joshi", "Ahmed", "Kulkarni"]


def grocery():
    P = [("G001", "Toned milk 1L", "Dairy", "Sunrise Dairy", 52, 58), ("G002", "Curd 500g", "Dairy", "Sunrise Dairy", 30, 36), ("G003", "Paneer 200g", "Dairy", "Sunrise Dairy", 70, 85),
         ("G004", "Basmati rice 5kg", "Staples", "Annapurna Traders", 480, 560), ("G005", "Toor dal 1kg", "Staples", "Annapurna Traders", 125, 148), ("G006", "Atta 10kg", "Staples", "Annapurna Traders", 360, 420),
         ("G007", "Sunflower oil 1L", "Staples", "Annapurna Traders", 128, 150), ("G008", "Sugar 1kg", "Staples", "Annapurna Traders", 40, 46), ("G009", "Tea 500g", "Beverages", "Hill Leaf", 210, 255),
         ("G010", "Instant coffee 100g", "Beverages", "Hill Leaf", 230, 280), ("G011", "Biscuits family pack", "Snacks", "Crunch Foods", 45, 60), ("G012", "Namkeen 400g", "Snacks", "Crunch Foods", 70, 95),
         ("G013", "Bread", "Bakery", "Daily Bake", 32, 40), ("G014", "Eggs (12)", "Dairy", "Sunrise Dairy", 72, 84), ("G015", "Detergent 2kg", "Household", "CleanCo", 180, 225),
         ("G016", "Dishwash bar", "Household", "CleanCo", 18, 25), ("G017", "Toothpaste", "Personal care", "CleanCo", 85, 105), ("G018", "Shampoo 340ml", "Personal care", "CleanCo", 190, 240),
         ("G019", "Imported olive oil", "Staples", "Gourmet Imports", 610, 690), ("G020", "Quinoa 500g", "Staples", "Gourmet Imports", 290, 340)]

    def tweak(o, d, rng):
        if o["delivery_mode"] == "QuickDrop courier" and rng.random() < 0.13: o["status"] = "Returned"           # story: one delivery partner, many returns
        if o["branch"] == "Jayanagar" and d >= date(2026, 4, 1) and rng.random() < 0.35: o["status"] = "Cancelled"  # story: a branch slipping
    return build({"seed": 11, "prefix": "KS", "customers": 900, "per_day": 18, "items_per_order": 3.2, "background": [("Returned", 0.03), ("Cancelled", 0.02)],
                  "cities": ["Bengaluru"], "products": P, "popularity": [9, 7, 5, 3, 5, 3, 5, 6, 4, 2, 8, 6, 8, 6, 3, 5, 4, 2, 0.4, 0.3],
                  "peaks": {10: 1.25, 11: 1.15, 4: 0.9}, "weekday": [1.0, 1.0, 0.7, 1.0, 1.05, 1.3, 1.35],
                  "order_cols": [("branch", ["Jayanagar", "Indiranagar", "Whitefield"], [0.34, 0.36, 0.30]),
                                 ("payment_mode", ["UPI", "Cash", "Card"], [0.62, 0.28, 0.10]),
                                 ("delivery_mode", ["Store pickup", "QuickDrop courier", "Own rider"], [0.5, 0.25, 0.25]),
                                 ("offer_code", ["No offer", "COMBO5", "FESTIVE10"], [0.82, 0.12, 0.06]),
                                 ("status", ["Completed"], [1.0])],
                  "discount": lambda o: {"COMBO5": 0.12, "FESTIVE10": 0.10}.get(o["offer_code"], 0.0),
                  "tweak": tweak, "dead": ["G019", "G020"]})


def boutique():
    P = [("B001", "Cotton kurta", "Kurtas", "Jaipur Looms", 420, 999), ("B002", "Silk kurta", "Kurtas", "Banaras Silks", 1100, 2499), ("B003", "Anarkali dress", "Dresses", "Jaipur Looms", 900, 2199),
         ("B004", "Maxi dress", "Dresses", "Urban Thread", 650, 1599), ("B005", "Palazzo pants", "Bottoms", "Urban Thread", 300, 799), ("B006", "Jeans", "Bottoms", "Denim Hub", 700, 1699),
         ("B007", "Dupatta", "Accessories", "Jaipur Looms", 150, 449), ("B008", "Handbag", "Accessories", "Leather Lane", 800, 1899), ("B009", "Silk saree", "Sarees", "Banaras Silks", 2600, 5999),
         ("B010", "Cotton saree", "Sarees", "Handloom Co-op", 900, 1999), ("B011", "Co-ord set", "Dresses", "Urban Thread", 850, 1999), ("B012", "Ethnic jacket", "Jackets", "Jaipur Looms", 950, 2299),
         ("B013", "Linen shirt", "Tops", "Urban Thread", 500, 1199), ("B014", "Crop top", "Tops", "Urban Thread", 280, 699), ("B015", "Velvet blazer", "Jackets", "Urban Thread", 1700, 3499)]

    def tweak(o, d, rng):
        if o["channel"] == "Website" and rng.random() < 0.17: o["status"] = "Returned"        # story: website orders come back (sizing)
        if o["channel"] == "Store" and rng.random() < (d - START).days / 1500: o["channel"] = "Instagram"  # story: Instagram keeps growing
    spec = {"seed": 22, "prefix": "TB", "customers": 1400, "per_day": 9, "items_per_order": 1.6, "gender_p": [0.82, 0.18], "background": [("Returned", 0.05), ("Cancelled", 0.02)],
            "cities": ["Hyderabad", "Bengaluru", "Chennai", "Pune", "Mumbai"], "products": P,
            "popularity": [10, 4, 5, 6, 7, 6, 8, 3, 2, 4, 5, 3, 5, 6, 0.3],
            "peaks": {10: 1.7, 11: 1.5, 3: 1.15, 6: 0.8, 7: 0.75}, "weekday": [0.85, 0.85, 0.9, 0.95, 1.05, 1.3, 1.25],
            "order_cols": [("channel", ["Store", "Website", "Instagram"], [0.5, 0.3, 0.2]),
                           ("coupon", ["No coupon", "FEST30", "NEW10"], [0.78, 0.12, 0.10]),
                           ("ship_mode", ["In store", "Standard", "Express"], [0.5, 0.35, 0.15]),
                           ("status", ["Delivered"], [1.0])],
            "discount": lambda o: {"FEST30": 0.30, "NEW10": 0.10}.get(o["coupon"], 0.0), "tweak": tweak, "dead": ["B015"]}
    return build(spec)


def cafe():
    P = [("M01", "Filter coffee", "Coffee", "Coorg Estates", 18, 60), ("M02", "Cappuccino", "Coffee", "Coorg Estates", 35, 160), ("M03", "Cold brew", "Coffee", "Coorg Estates", 40, 190),
         ("M04", "Masala chai", "Tea", "Hill Leaf", 12, 50), ("M05", "Green tea", "Tea", "Hill Leaf", 15, 90), ("M06", "Veg sandwich", "Food", "Daily Bake", 45, 150),
         ("M07", "Chicken wrap", "Food", "Daily Bake", 80, 220), ("M08", "Croissant", "Bakery", "Daily Bake", 35, 120), ("M09", "Chocolate brownie", "Bakery", "Daily Bake", 30, 130),
         ("M10", "Blueberry muffin", "Bakery", "Daily Bake", 32, 110), ("M11", "Fresh lime soda", "Coolers", "Fresh Press", 15, 90), ("M12", "Mango smoothie", "Coolers", "Fresh Press", 45, 180)]

    def tweak(o, d, rng):
        if o["staff"] == "Counter 3" and rng.random() < 0.09: o["status"] = "Refunded"      # story: one counter, many refunds
    return build({"seed": 33, "prefix": "CF", "customers": 1100, "per_day": 32, "items_per_order": 1.7, "background": [("Refunded", 0.015)], "qty": 0.2,
                  "cities": ["Bengaluru"], "products": P, "popularity": [10, 9, 5, 9, 2, 6, 4, 5, 4, 3, 4, 3],
                  "peaks": {4: 1.15, 5: 1.2, 12: 1.1, 7: 0.85}, "weekday": [0.85, 0.85, 0.9, 0.9, 1.0, 1.45, 1.5],
                  "order_cols": [("outlet", ["Koramangala", "HSR Layout"], [0.62, 0.38]),
                                 ("order_type", ["Dine-in", "Takeaway", "Delivery app"], [0.5, 0.3, 0.2]),
                                 ("staff", ["Counter 1", "Counter 2", "Counter 3"], [0.4, 0.35, 0.25]),
                                 ("payment_mode", ["UPI", "Card", "Cash"], [0.7, 0.18, 0.12]),
                                 ("status", ["Paid"], [1.0])],
                  "discount": lambda o: 0.15 if o["order_type"] == "Delivery app" else 0.0, "tweak": tweak, "stock": False})


TOURS = {
    "grocery": [
        ("overview", "Start with the briefing", "The dark panel sums up the whole store: the key numbers for the last full month and how many things need attention."),
        ("alerts", "One branch is slipping", "Jayanagar's cancellations jumped from April 2026. Alerts puts it first, with what to check."),
        ("suggestions", "A courier with many returns", "Orders sent through QuickDrop courier come back about 5x as often. Open the finding to see the rows behind it."),
        ("products", "Best sellers on empty shelves", "Three of the store's best sellers are out of stock, and two imported items have not sold at all."),
        ("whatif", "Try a change", "Move the discount slider to see what the COMBO5 offer costs in profit."),
    ],
    "boutique": [
        ("overview", "Start with the briefing", "The dark panel sums up the boutique: revenue, profit and what needs attention."),
        ("alerts", "Website orders come back", "Orders from the website are returned about 4x as often as store or Instagram orders. Sizing is the usual reason."),
        ("suggestions", "A coupon that costs too much", "FEST30 brings in orders, but its profit margin is about 17 points lower."),
        ("trends", "Instagram is growing", "Instagram's share keeps rising month after month, and October and November peak every year."),
        ("customers", "Regulars who stopped coming", "A group of regular customers has gone quiet. They are worth a call or a message."),
    ],
    "cafe": [
        ("overview", "Start with the briefing", "The dark panel sums up both outlets: sales, profit and what needs attention."),
        ("alerts", "One counter, many refunds", "Counter 3 refunds about 8x as often as the others. Worth checking training or the till."),
        ("suggestions", "Delivery apps earn less per order", "Delivery-app orders are about 15% smaller after the app discount."),
        ("trends", "Weekends carry the café", "Saturday and Sunday are far busier than weekdays. Plan staff and stock around them."),
        ("hood", "See how Alpha did it", "Every step from reading the files to the checks is listed here, in order."),
    ],
}

SAMPLES = [
    ("grocery", "Sri Krishna Stores", "Neighbourhood grocery store with 3 branches in Bengaluru", grocery),
    ("boutique", "Tara Boutique", "Women's clothing sold in store, online and on Instagram", boutique),
    ("cafe", "Bean There Café", "Two-outlet café with dine-in, takeaway and delivery apps", cafe),
]

if __name__ == "__main__":
    index = []
    for key, name, about, fn in SAMPLES:
        tables = fn()
        folder = os.path.join(OUT, key)
        os.makedirs(folder, exist_ok=True)
        files = []
        for t, df in tables.items():
            fname = f"sample-{key}-{t.replace('_', '-')}.csv"
            df.to_csv(os.path.join(folder, fname), index=False)
            files.append(fname)
            print(key, fname, len(df))
        index.append({"key": key, "name": name, "about": about, "files": files,
                      "tour": [{"section": a, "title": b, "text": c} for a, b, c in TOURS[key]]})
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(index, f, indent=2)

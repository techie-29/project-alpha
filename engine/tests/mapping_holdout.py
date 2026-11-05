"""Held-out files for column reading: written AFTER the rules were tuned on mapping_cases.py and not used to tune them.
The score on this set is the honest accuracy figure. Different businesses and header styles from the main set."""
from __future__ import annotations
import numpy as np
import pandas as pd

N = 400


def _r(s):
    return np.random.default_rng(100 + s)


def _d(n, freq="7h", start="2024-02-01"):
    return pd.date_range(start, periods=n, freq=freq)


def grocery_app(s=1):
    r = _r(s); n = N
    df = pd.DataFrame({"OrderNo": [str(x) for x in r.integers(700000, 700390, n)], "Order Placed At": _d(n).strftime("%Y-%m-%d %H:%M"), "Cust Code": [f"CU{x:04d}" for x in r.integers(1, 150, n)],
                       "Basket Value": np.round(r.gamma(3, 150, n), 2), "Delivery Fee": r.choice([0, 25, 40], n), "Items Count": r.integers(1, 25, n),
                       "City Zone": r.choice(["Zone A", "Zone B", "Zone C"], n), "Payment Method": r.choice(["UPI", "Card", "COD"], n), "Rider": r.choice([f"R{i}" for i in range(15)], n)})
    exp = {"OrderNo": "order_id", "Order Placed At": "event_date", "Cust Code": "customer_id", "Basket Value": "revenue", "Delivery Fee": {"expense", "revenue", "money_other"},
           "Items Count": "quantity", "City Zone": "location", "Payment Method": "payment_method", "Rider": "employee_id"}
    return "app_orders.csv", df, exp


def garage(s=2):
    r = _r(s); n = N
    lab = r.choice([500, 800, 1500], n); parts = np.round(r.uniform(0, 6000, n), 2)
    df = pd.DataFrame({"Job Card No": [f"JC{i:05d}" for i in range(n)], "Job Date": _d(n, "1D").strftime("%d/%m/%Y"), "Service Type": r.choice(["General", "Repair", "Denting"], n),
                       "Labour Charges": lab, "Parts Cost": parts, "Total Bill": np.round(lab + parts, 2), "Mechanic": r.choice(["M1", "M2", "M3", "M4"], n), "Customer Rating": r.choice([3, 4, 5], n)})
    exp = {"Job Card No": "order_id", "Job Date": "event_date", "Service Type": "product_group", "Labour Charges": {"revenue", "money_other", "expense"},
           "Parts Cost": "cost", "Total Bill": "revenue", "Mechanic": "employee_id", "Customer Rating": "rating"}
    return "jobs.csv", df, exp


def gym(s=3):
    r = _r(s); n = 300
    df = pd.DataFrame({"Member No": [f"G{i:04d}" for i in range(n)], "Joining Date": _d(n, "1D", "2023-01-01").strftime("%Y-%m-%d"), "Membership Type": r.choice(["Monthly", "Quarterly", "Annual"], n),
                       "Fee Paid": r.choice([1500, 4000, 12000], n), "Trainer": r.choice(["T1", "T2", "T3"], n), "Age": r.integers(18, 65, n), "Gender": r.choice(["M", "F"], n)})
    exp = {"Member No": "customer_id", "Joining Date": "signup_date", "Membership Type": "segment", "Fee Paid": "revenue", "Trainer": "employee_id", "Age": "age", "Gender": "gender"}
    return "members.csv", df, exp


def electronics(s=4):
    r = _r(s); n = N
    u = r.integers(1, 4, n); sp = r.choice([999.0, 4999.0, 15999.0, 45999.0], n); cp = np.round(sp * r.uniform(0.7, 0.9, n), 2)
    df = pd.DataFrame({"Txn ID": [f"T{i:06d}" for i in range(n)], "Txn Date": _d(n).strftime("%d-%m-%Y"), "SKU Code": [f"E{x:04d}" for x in r.integers(1, 120, n)],
                       "Brand": r.choice(["Brand A", "Brand B", "Brand C"], n), "Units": u, "Selling Price": sp, "Cost Price": cp, "Gross Profit": np.round(u * (sp - cp), 2),
                       "Store Code": r.choice(["S01", "S02", "S03"], n), "Salesperson": r.choice(["P1", "P2", "P3", "P4"], n)})
    exp = {"Txn ID": "order_id", "Txn Date": "event_date", "SKU Code": "product_id", "Brand": "product_group", "Units": "quantity", "Selling Price": "unit_price",
           "Cost Price": "unit_cost", "Gross Profit": "profit", "Store Code": "site_id", "Salesperson": "employee_id"}
    return "store_sales.csv", df, exp


def grn(s=5):
    r = _r(s); n = N
    q = r.integers(5, 300, n); rate = r.choice([12.0, 35.5, 80.0], n)
    df = pd.DataFrame({"GRN No": [f"GRN{i:05d}" for i in range(n)], "GRN Date": _d(n, "1D").strftime("%Y-%m-%d"), "Supplier Name": r.choice([f"Supp {i}" for i in range(10)], n),
                       "Item": r.choice([f"Item {i}" for i in range(80)], n), "Received Qty": q, "Rate": rate, "Amount": np.round(q * rate, 2), "Invoice No": [f"SI{x}" for x in r.integers(100, 500, n)]})
    exp = {"GRN No": "order_id", "GRN Date": "event_date", "Supplier Name": "supplier_id", "Item": "product_id", "Received Qty": "units_received", "Rate": "unit_cost", "Amount": "cost"}
    return "goods_received.csv", df, exp


def snake_export(s=6):
    r = _r(s); n = N
    q = r.integers(1, 9, n); px = r.choice([4.5, 9.0, 22.0], n); d = np.round(q * px * r.choice([0, 0, 0.1], n), 2)
    df = pd.DataFrame({"txn_dt": _d(n).strftime("%Y-%m-%d"), "cust_id": [f"c{x}" for x in r.integers(1, 200, n)], "prod_cd": [f"p{x:03d}" for x in r.integers(1, 90, n)],
                       "qty_sold": q, "unit_px": px, "disc_amt": d, "net_rev": np.round(q * px - d, 2), "region_nm": r.choice(["north", "south", "east", "west"], n)})
    exp = {"txn_dt": "event_date", "cust_id": "customer_id", "prod_cd": "product_id", "qty_sold": "quantity", "unit_px": "unit_price", "disc_amt": "discount",
           "net_rev": "revenue", "region_nm": "location"}
    return "export.csv", df, exp


def food_delivery(s=7):
    r = _r(s); n = N
    df = pd.DataFrame({"order_ref": [f"OD{i:06d}" for i in range(n)], "ordered_on": _d(n, "3h").strftime("%Y-%m-%d %H:%M"), "restaurant": r.choice([f"Rest {i}" for i in range(25)], n),
                       "cuisine": r.choice(["North Indian", "Chinese", "Pizza"], n), "order_total": np.round(r.gamma(2.5, 180, n), 2), "tip_amount": r.choice([0, 0, 20, 50], n),
                       "prep_time_min": r.integers(5, 45, n), "delivery_time_min": r.integers(10, 70, n), "stars": r.choice([1, 2, 3, 4, 5], n)})
    exp = {"order_ref": "order_id", "ordered_on": "event_date", "restaurant": {"site_id", "supplier_id", "name_label", "group"}, "cuisine": "product_group",
           "order_total": "revenue", "prep_time_min": "duration", "delivery_time_min": "duration", "stars": "rating"}
    return "deliveries.csv", df, exp


def french_shop(s=8):
    r = _r(s); n = N
    q = r.integers(1, 6, n); pu = r.choice([3.2, 7.9, 15.0], n)
    df = pd.DataFrame({"Date de vente": _d(n).strftime("%d/%m/%Y"), "N° facture": [f"F{x}" for x in r.integers(1000, 1350, n)], "Client": [f"CL{x:03d}" for x in r.integers(1, 150, n)],
                       "Quantité": q, "Prix unitaire": pu, "Montant": np.round(q * pu, 2), "Remise": np.round(q * pu * r.choice([0, 0.05], n), 2), "Magasin": r.choice(["Paris", "Lyon", "Nice"], n)})
    exp = {"Date de vente": "event_date", "N° facture": "order_id", "Client": "customer_id", "Quantité": "quantity", "Prix unitaire": "unit_price", "Montant": "revenue",
           "Remise": "discount", "Magasin": {"site_id", "location"}}
    return "ventes.csv", df, exp


ALL = [grocery_app, garage, gym, electronics, grn, snake_export, food_delivery, french_shop]


def cases():
    return [f() for f in ALL]

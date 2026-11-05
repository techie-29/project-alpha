"""Blind set: written after all tuning, scored once to report honest accuracy. Do not tune rules against this file;
add a new blind set instead when the rules change."""
from __future__ import annotations
import numpy as np
import pandas as pd

N = 400


def _r(s):
    return np.random.default_rng(500 + s)


def _d(n, freq="5h", start="2024-03-01"):
    return pd.date_range(start, periods=n, freq=freq)


def shopify(s=1):
    r = _r(s); n = N
    sub = np.round(r.gamma(2, 900, n), 2); ship = r.choice([0, 49, 99], n); tax = np.round(sub * 0.18, 2); disc = np.round(sub * r.choice([0, 0, 0.1], n), 2)
    df = pd.DataFrame({"Name": [f"#{1000 + i}" for i in range(n)], "Email": [f"u{i}@x.com" for i in r.integers(0, 200, n)], "Financial Status": r.choice(["paid", "paid", "refunded", "pending"], n),
                       "Created at": _d(n).strftime("%Y-%m-%d %H:%M:%S +0530"), "Subtotal": sub, "Shipping": ship, "Taxes": tax, "Discount Amount": disc, "Total": np.round(sub + ship + tax - disc, 2),
                       "Lineitem quantity": r.integers(1, 5, n), "Lineitem price": r.choice([299.0, 799.0, 1499.0], n), "Lineitem sku": [f"SH-{x:03d}" for x in r.integers(1, 80, n)],
                       "Vendor": r.choice(["Brand X", "Brand Y"], n)})
    exp = {"Name": "order_id", "Email": "personal", "Financial Status": "status", "Created at": "event_date", "Subtotal": "gross_revenue", "Shipping": {"expense", "revenue", "money_other"},
           "Taxes": "tax", "Discount Amount": "discount", "Total": "revenue", "Lineitem quantity": "quantity", "Lineitem price": "unit_price", "Lineitem sku": "product_id",
           "Vendor": {"supplier_id", "product_group"}}
    return "orders_export.csv", df, exp


def square_pos(s=2):
    r = _r(s); n = N
    g = r.choice([150.0, 220.0, 90.0, 310.0], n); d = r.choice([0.0, 0.0, 20.0], n); t = np.round((g - d) * 0.05, 2)
    df = pd.DataFrame({"Date": _d(n, "2h").strftime("%m/%d/%Y"), "Time": _d(n, "2h").strftime("%H:%M:%S"), "Category": r.choice(["Coffee", "Tea", "Bakery"], n), "Item": r.choice([f"Item {i}" for i in range(30)], n),
                       "Qty": r.integers(1, 3, n), "Gross Sales": g, "Discounts": d, "Net Sales": g - d, "Tax": t, "Transaction ID": [f"tx{i:06d}" for i in range(n)],
                       "Payment ID": [f"pay{i:06d}" for i in range(n)], "Device Name": r.choice(["Counter 1", "Counter 2"], n)})
    exp = {"Date": "event_date", "Category": "product_group", "Item": "product_id", "Qty": "quantity", "Gross Sales": "gross_revenue", "Discounts": "discount",
           "Net Sales": "revenue", "Tax": "tax", "Transaction ID": "order_id"}
    return "items_sales.csv", df, exp


def stock_count(s=3):
    r = _r(s); n = 360
    dates = np.repeat(pd.date_range("2024-01-31", periods=6, freq="ME"), 60)
    items = np.tile([f"I-{i:04d}" for i in range(60)], 6)
    df = pd.DataFrame({"Count Date": pd.Series(dates).dt.strftime("%Y-%m-%d"), "Item No.": items, "Location": np.tile(r.choice(["Main WH", "Shop Floor"], 60), 6),
                       "On Hand Qty": r.integers(0, 500, n), "Unit Cost": np.tile(np.round(r.uniform(5, 90, 60), 2), 6), "Bin": np.tile([f"B{i % 12}" for i in range(60)], 6)})
    exp = {"Count Date": {"snapshot_date", "event_date"}, "Item No.": "product_id", "Location": {"site_id", "location"}, "On Hand Qty": "stock_level", "Unit Cost": "unit_cost"}
    return "stock_count.csv", df, exp


def spanish_restaurant(s=4):
    r = _r(s); n = N
    u = r.integers(1, 4, n); pr = r.choice([3.5, 8.0, 12.5, 18.0], n)
    df = pd.DataFrame({"Fecha": _d(n, "1h").strftime("%d/%m/%Y"), "Ticket": [str(x) for x in r.integers(30000, 30300, n)], "Mesa": r.integers(1, 20, n), "Camarero": r.choice(["Luis", "Ana", "Pepe"], n),
                       "Producto": r.choice([f"Plato {i}" for i in range(25)], n), "Unidades": u, "Precio": pr, "Total": np.round(u * pr, 2)})
    exp = {"Fecha": "event_date", "Ticket": "order_id", "Camarero": "employee_id", "Producto": "product_id", "Unidades": "quantity", "Precio": "unit_price", "Total": "revenue"}
    return "ventas_restaurante.csv", df, exp


def wholesale_invoice(s=5):
    r = _r(s); n = N
    q = r.integers(1, 100, n); rate = r.choice([45.0, 120.0, 560.0], n); tv = np.round(q * rate, 2)
    df = pd.DataFrame({"Inv No": [f"WS/{x}" for x in r.integers(100, 400, n)], "Inv Date": _d(n, "13h").strftime("%d-%m-%Y"), "Party": r.choice([f"Retailer {i}" for i in range(40)], n),
                       "HSN": r.choice(["3004", "8471", "6109"], n), "Item Name": r.choice([f"Product {i}" for i in range(60)], n), "Qty": q, "Rate": rate, "Taxable Value": tv,
                       "IGST": np.round(tv * 0.18, 2), "Invoice Value": np.round(tv * 1.18, 2), "Salesman": r.choice(["S1", "S2"], n)})
    exp = {"Inv No": "order_id", "Inv Date": "event_date", "Party": "customer_id", "Item Name": "product_id", "Qty": "quantity", "Rate": "unit_price",
           "Taxable Value": {"gross_revenue", "revenue"}, "IGST": "tax", "Invoice Value": "revenue", "Salesman": "employee_id"}
    return "sales_invoices.csv", df, exp


def pharmacy_bills(s=6):
    r = _r(s); n = N
    q = r.integers(1, 6, n); mrp = r.choice([35.0, 120.0, 480.0], n); dp = r.choice([0, 10, 15], n)
    df = pd.DataFrame({"Bill Dt": _d(n, "2h").strftime("%d/%m/%Y"), "Bill#": [str(x) for x in r.integers(90000, 90350, n)], "Patient Name": [f"Person {i}" for i in r.integers(1, 200, n)],
                       "Drug": r.choice([f"Drug {i}" for i in range(70)], n), "Batch": [f"B{x}" for x in r.integers(100, 900, n)], "Qty": q, "MRP": mrp, "Disc%": dp,
                       "Amount": np.round(q * mrp * (1 - dp / 100), 2), "Doctor": r.choice(["Dr A", "Dr B", "Dr C"], n)})
    exp = {"Bill Dt": "event_date", "Bill#": "order_id", "Patient Name": "personal", "Drug": "product_id", "Qty": "quantity", "MRP": "unit_price",
           "Disc%": "discount_pct", "Amount": "revenue"}
    return "pharmacy_bills.csv", df, exp


ALL = [shopify, square_pos, stock_count, spanish_restaurant, wholesale_invoice, pharmacy_bills]


def cases():
    return [f() for f in ALL]

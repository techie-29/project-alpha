"""A labelled set of realistic business files for measuring how well columns are read.

Each case is a small generated table whose headers and value shapes follow common real exports (online shops, POS tills,
pharmacy stock, purchase registers, clinics, hotels, marketing, Tally-style registers, master lists...). The expected meaning
is given for the columns that matter; a set means several answers are acceptable. Nothing here is modelled on one
particular dataset: the point is to cover many kinds of business and many ways of writing the same header."""
from __future__ import annotations
import numpy as np
import pandas as pd

N = 400


def _rng(seed):
    return np.random.default_rng(seed)


def _dates(n, start="2023-01-01", freq="9h"):
    return pd.date_range(start, periods=n, freq=freq)


def _ids(prefix, n, pool, r, width=5):
    return [f"{prefix}{i:0{width}d}" for i in r.integers(1, pool, n)]


def superstore(seed=1):
    r = _rng(seed); n = N
    qty = r.integers(1, 10, n); price = r.choice([9.99, 24.5, 79.0, 249.0, 15.25], n); disc = r.choice([0, 0, 0.1, 0.2, 0.3, 0.5], n)
    sales = np.round(qty * price * (1 - disc), 2); profit = np.round(sales * r.uniform(-0.4, 0.35, n), 2)
    od = _dates(n)
    df = pd.DataFrame({"Row ID": range(1, n + 1), "Order ID": _ids("CA-2023-", n, 300, r, 6), "Order Date": od.strftime("%m/%d/%Y"),
                       "Ship Date": (od + pd.to_timedelta(r.integers(0, 6, n), "D")).strftime("%m/%d/%Y"), "Ship Mode": r.choice(["Standard Class", "Second Class", "First Class", "Same Day"], n),
                       "Customer ID": _ids("CG-", n, 120, r), "Customer Name": [f"Person {i}" for i in r.integers(1, 120, n)], "Segment": r.choice(["Consumer", "Corporate", "Home Office"], n),
                       "City": r.choice([f"City {i}" for i in range(60)], n), "State": r.choice([f"State {i}" for i in range(20)], n), "Region": r.choice(["East", "West", "Central", "South"], n),
                       "Product ID": _ids("FUR-", n, 150, r, 8), "Category": r.choice(["Furniture", "Technology", "Office Supplies"], n), "Sub-Category": r.choice([f"Sub {i}" for i in range(17)], n),
                       "Sales": sales, "Quantity": qty, "Discount": disc, "Profit": profit})
    exp = {"Order ID": "order_id", "Order Date": "event_date", "Ship Date": "done_date", "Ship Mode": "delivery_method", "Customer ID": "customer_id",
           "Customer Name": "personal", "Segment": "segment", "City": "location", "State": "location", "Region": "location", "Product ID": "product_id",
           "Category": "product_group", "Sub-Category": "product_group", "Sales": "revenue", "Quantity": "quantity", "Discount": "discount_pct", "Profit": "profit"}
    return "superstore_orders.csv", df, exp


def online_retail(seed=2):
    r = _rng(seed); n = N
    qty = r.integers(1, 24, n); qty[r.random(n) < 0.03] *= -1
    df = pd.DataFrame({"Invoice": [str(x) for x in r.integers(489000, 489300, n)], "StockCode": _ids("", n, 900, r, 5), "Description": [f"ITEM DESCRIPTION {i}" for i in r.integers(1, 300, n)],
                       "Quantity": qty, "InvoiceDate": _dates(n, freq="3h").strftime("%d-%m-%Y %H:%M"), "Price": r.choice([0.85, 1.25, 2.95, 4.95, 12.75], n),
                       "Customer ID": [str(x) for x in r.integers(12000, 12400, n)], "Country": r.choice(["United Kingdom", "France", "Germany", "EIRE"], n)})
    exp = {"Invoice": "order_id", "StockCode": "product_id", "Quantity": "quantity", "InvoiceDate": "event_date", "Price": "unit_price",
           "Customer ID": "customer_id", "Country": "location", "Description": {"name_label", "free_text"}}
    return "online_retail.csv", df, exp


def restaurant_pos(seed=3):
    r = _rng(seed); n = N
    qty = r.integers(1, 5, n); rate = r.choice([120, 180, 250, 90, 340], n); amt = qty * rate; tax = np.round(amt * 0.05, 2)
    df = pd.DataFrame({"Bill No": [f"B{x}" for x in r.integers(1000, 1300, n)], "Date": _dates(n, freq="2h").strftime("%d/%m/%Y"), "Item Name": r.choice([f"Dish {i}" for i in range(40)], n),
                       "Qty": qty, "Rate": rate, "Amount": amt, "GST": tax, "Payment Mode": r.choice(["Cash", "UPI", "Card"], n), "Waiter": r.choice([f"W{i}" for i in range(8)], n)})
    exp = {"Bill No": "order_id", "Date": "event_date", "Item Name": "product_id", "Qty": "quantity", "Rate": "unit_price", "Amount": "revenue",
           "GST": "tax", "Payment Mode": "payment_method", "Waiter": "employee_id"}
    return "pos_sales.csv", df, exp


def pharmacy_stock(seed=4):
    r = _rng(seed); n = 300
    df = pd.DataFrame({"Item Code": _ids("MED", n, 2000, r, 4), "Item": [f"Medicine {i}" for i in range(n)], "Batch No": _ids("BT", n, 9000, r, 5),
                       "Expiry Date": (pd.Timestamp("2025-06-01") + pd.to_timedelta(r.integers(0, 700, n), "D")).strftime("%Y-%m-%d"),
                       "Qty On Hand": r.integers(0, 400, n), "MRP": r.choice([12.5, 45.0, 99.0, 150.0, 320.0], n), "Purchase Rate": r.choice([8.0, 30.0, 70.0, 110.0, 250.0], n),
                       "Supplier": r.choice([f"Supplier {i}" for i in range(12)], n), "Reorder Level": r.choice([20, 50, 100], n)})
    exp = {"Item Code": "product_id", "Expiry Date": "expiry_date", "Qty On Hand": "stock_level", "MRP": "unit_price", "Purchase Rate": "unit_cost",
           "Supplier": "supplier_id", "Reorder Level": "reorder_level"}
    return "stock_list.csv", df, exp


def purchase_orders(seed=5):
    r = _rng(seed); n = N
    q = r.integers(10, 500, n); rec = np.minimum(q, (q * r.uniform(0.7, 1.05, n)).astype(int)); cost = r.choice([5.5, 12.0, 30.0, 75.0], n)
    pod = _dates(n, freq="1D")
    df = pd.DataFrame({"PO Number": [f"PO-{i:05d}" for i in range(n)], "PO Date": pod.strftime("%Y-%m-%d"), "Vendor": r.choice([f"Vendor {i}" for i in range(15)], n),
                       "Item Code": _ids("IT", n, 300, r, 4), "Qty Ordered": q, "Qty Received": rec, "Unit Cost": cost, "Total Cost": np.round(q * cost, 2),
                       "Expected Date": (pod + pd.Timedelta(days=7)).strftime("%Y-%m-%d"), "Received Date": (pod + pd.to_timedelta(r.integers(4, 14, n), "D")).strftime("%Y-%m-%d")})
    exp = {"PO Number": "order_id", "PO Date": "event_date", "Vendor": "supplier_id", "Item Code": "product_id", "Qty Ordered": "units_ordered",
           "Qty Received": "units_received", "Unit Cost": "unit_cost", "Total Cost": "cost", "Expected Date": "due_date", "Received Date": "done_date"}
    return "purchase_orders.csv", df, exp


def ecommerce_orders(seed=6):
    r = _rng(seed); n = N
    df = pd.DataFrame({"order_id": [f"{x:032x}" for x in r.integers(1, 2**60, n)], "customer_unique_id": [f"{x:032x}" for x in r.integers(1, 200, n)],
                       "order_purchase_timestamp": _dates(n, freq="5h").strftime("%Y-%m-%d %H:%M:%S"), "order_status": r.choice(["delivered", "delivered", "delivered", "canceled", "shipped"], n),
                       "payment_type": r.choice(["credit_card", "boleto", "voucher", "debit_card"], n), "payment_value": np.round(r.gamma(2, 80, n), 2),
                       "freight_value": np.round(r.uniform(5, 40, n), 2), "review_score": r.choice([1, 2, 3, 4, 5, 5, 5], n), "delivery_days": r.integers(2, 30, n)})
    exp = {"order_id": "order_id", "customer_unique_id": "customer_id", "order_purchase_timestamp": "event_date", "order_status": "status", "payment_type": "payment_method",
           "payment_value": "revenue", "freight_value": "expense", "review_score": "rating", "delivery_days": "duration"}
    return "orders.csv", df, exp


def clinic(seed=7):
    r = _rng(seed); n = N
    df = pd.DataFrame({"Appointment ID": [f"AP{i:05d}" for i in range(n)], "Patient ID": _ids("P", n, 250, r, 4), "Doctor": r.choice([f"Dr {i}" for i in range(9)], n),
                       "Department": r.choice(["Cardiology", "Ortho", "General", "ENT"], n), "Appointment Date": _dates(n, freq="4h").strftime("%d-%m-%Y"),
                       "Consultation Fee": r.choice([300, 500, 800, 1200], n), "Status": r.choice(["Attended", "Attended", "No-show", "Cancelled"], n),
                       "Wait Time (mins)": r.integers(0, 90, n), "Rating": r.choice([1, 2, 3, 4, 5], n)})
    exp = {"Appointment ID": "order_id", "Patient ID": "customer_id", "Doctor": "employee_id", "Department": "product_group", "Appointment Date": "event_date",
           "Consultation Fee": "revenue", "Status": "status", "Wait Time (mins)": "duration", "Rating": "rating"}
    return "appointments.csv", df, exp


def wholesale_lines(seed=8):
    r = _rng(seed); n = N
    q = r.integers(1, 60, n); up = r.choice([3.5, 8.99, 20.0, 45.5, 120.0], n); d = np.round(r.choice([0.0, 0.01, 0.03, 0.05, 0.07, 0.1], n), 2)
    sales = np.round(q * up * (1 - d), 2); fr = np.round(r.uniform(1, 40, n), 2)
    df = pd.DataFrame({"Order No": [f"SO{x}" for x in r.integers(10000, 10300, n)], "Order Date": _dates(n, freq="11h").strftime("%Y-%m-%d"), "Customer": _ids("C", n, 90, r, 4),
                       "Order Quantity": q, "Unit Price": up, "Discount offered": d, "Sales": sales, "Shipping Cost": fr, "Profit": np.round(sales * r.uniform(-0.2, 0.3, n), 2),
                       "Ship Mode": r.choice(["Air", "Truck", "Express"], n), "Priority": r.choice(["High", "Low", "Medium", "Critical"], n)})
    exp = {"Order No": "order_id", "Order Date": "event_date", "Customer": "customer_id", "Order Quantity": "quantity", "Unit Price": "unit_price",
           "Discount offered": "discount_pct", "Sales": "revenue", "Shipping Cost": "expense", "Profit": "profit", "Ship Mode": "delivery_method", "Priority": "group"}
    return "sales_lines.csv", df, exp


def salon(seed=9):
    r = _rng(seed); n = N
    price = r.choice([300, 600, 1200, 2500], n); dp = r.choice([0, 0, 10, 15, 20], n); final = np.round(price * (1 - dp / 100), 2)
    df = pd.DataFrame({"Invoice No": [f"INV{i:05d}" for i in range(n)], "Date": _dates(n, freq="3h").strftime("%d/%m/%Y"), "Service": r.choice(["Haircut", "Color", "Spa", "Facial"], n),
                       "Stylist": r.choice(["Asha", "Ravi", "Meena", "John"], n), "Price": price, "Discount %": dp, "Final Amount": final, "Tip": r.choice([0, 0, 50, 100], n)})
    exp = {"Invoice No": "order_id", "Date": "event_date", "Service": {"product_group", "product_id"}, "Stylist": "employee_id", "Price": {"unit_price", "gross_revenue"},
           "Discount %": "discount_pct", "Final Amount": "revenue"}
    return "salon_invoices.csv", df, exp


def stock_ledger(seed=10):
    r = _rng(seed); n = N
    df = pd.DataFrame({"Date": _dates(n, freq="6h").strftime("%Y-%m-%d"), "SKU": _ids("SK", n, 60, r, 3), "Movement Type": r.choice(["IN", "OUT", "Sale", "Damaged", "Return"], n),
                       "Qty": r.integers(1, 50, n), "Warehouse": r.choice(["WH-North", "WH-South", "WH-East"], n)})
    exp = {"Date": "event_date", "SKU": "product_id", "Movement Type": "movement_type", "Qty": "quantity", "Warehouse": "site_id"}
    return "stock_movements.csv", df, exp


def hotel(seed=11):
    r = _rng(seed); n = N
    nights = r.integers(1, 8, n); adr = np.round(r.uniform(60, 250, n), 2)
    df = pd.DataFrame({"Booking ID": [f"BK{i:05d}" for i in range(n)], "Check-in Date": _dates(n, freq="7h").strftime("%Y-%m-%d"), "Nights": nights, "ADR": adr,
                       "Total Revenue": np.round(nights * adr, 2), "Room Type": r.choice(["Standard", "Deluxe", "Suite"], n), "Booking Channel": r.choice(["Online", "Direct", "Travel Agent"], n),
                       "Is Canceled": r.choice(["No", "No", "No", "Yes"], n), "Lead Time": r.integers(0, 200, n)})
    exp = {"Booking ID": "order_id", "Check-in Date": "event_date", "Nights": "quantity", "ADR": "unit_price", "Total Revenue": "revenue", "Room Type": "product_group",
           "Booking Channel": "channel", "Is Canceled": {"yes_no", "status"}, "Lead Time": "duration"}
    return "bookings.csv", df, exp


def marketing(seed=12):
    r = _rng(seed); n = 365
    imp = r.integers(5000, 90000, n); clicks = (imp * r.uniform(0.01, 0.05, n)).astype(int)
    df = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"), "Campaign": r.choice(["Spring Sale", "Diwali", "Brand"], n), "Channel": r.choice(["Google", "Facebook", "Email"], n),
                       "Impressions": imp, "Clicks": clicks, "Spend": np.round(clicks * r.uniform(0.2, 1.5, n), 2), "Conversions": (clicks * r.uniform(0.01, 0.08, n)).astype(int),
                       "Revenue": np.round(clicks * r.uniform(0.5, 4, n), 2)})
    exp = {"Date": "event_date", "Campaign": "campaign", "Channel": "channel", "Impressions": "activity_count", "Clicks": "activity_count", "Spend": "expense",
           "Conversions": "activity_count", "Revenue": "revenue"}
    return "marketing.csv", df, exp


def customer_master(seed=13):
    r = _rng(seed); n = 300
    df = pd.DataFrame({"Customer ID": [f"CU{i:05d}" for i in range(n)], "Name": [f"Person {i}" for i in range(n)], "Email": [f"p{i}@mail.com" for i in range(n)],
                       "City": r.choice([f"City {i}" for i in range(30)], n), "Signup Date": _dates(n, freq="1D").strftime("%Y-%m-%d"), "Age": r.integers(18, 75, n),
                       "Gender": r.choice(["Male", "Female"], n), "Loyalty Tier": r.choice(["Silver", "Gold", "Platinum"], n)})
    exp = {"Customer ID": "customer_id", "Name": "personal", "Email": "personal", "City": "location", "Signup Date": "signup_date", "Age": "age", "Gender": "gender", "Loyalty Tier": "segment"}
    return "customers.csv", df, exp


def product_master(seed=14):
    r = _rng(seed); n = 200
    cp = np.round(r.uniform(10, 400, n), 2)
    df = pd.DataFrame({"SKU": [f"SKU{i:04d}" for i in range(n)], "Product Name": [f"Product {i}" for i in range(n)], "Category": r.choice(["Snacks", "Drinks", "Dairy", "Home"], n),
                       "Brand": r.choice([f"Brand {i}" for i in range(12)], n), "Cost Price": cp, "Selling Price": np.round(cp * r.uniform(1.1, 1.6, n), 2), "Reorder Level": r.choice([10, 25, 50], n)})
    exp = {"SKU": "product_id", "Product Name": "name_label", "Category": "product_group", "Brand": "product_group", "Cost Price": "unit_cost", "Selling Price": "unit_price", "Reorder Level": "reorder_level"}
    return "products.csv", df, exp


def tally_register(seed=15):
    r = _rng(seed); n = N
    gross = np.round(r.uniform(500, 25000, n), 2); disc = np.round(gross * r.choice([0, 0.02, 0.05], n), 2); cg = np.round((gross - disc) * 0.09, 2)
    df = pd.DataFrame({"Voucher No": [f"SAL/{i:05d}" for i in range(n)], "Date": _dates(n, freq="13h").strftime("%d-%b-%Y"), "Party Name": r.choice([f"Traders {i}" for i in range(70)], n),
                       "Gross Total": gross, "Discount": disc, "CGST": cg, "SGST": cg, "Net Amount": np.round(gross - disc + 2 * cg, 2)})
    exp = {"Voucher No": "order_id", "Date": "event_date", "Party Name": "customer_id", "Gross Total": "gross_revenue", "Discount": "discount", "CGST": "tax", "SGST": "tax", "Net Amount": "revenue"}
    return "sales_register.csv", df, exp


def weekly_store(seed=16):
    r = _rng(seed); n = 156
    wk = pd.date_range("2023-01-02", periods=52, freq="W-MON")
    df = pd.DataFrame({"Week": np.tile(wk.strftime("%Y-%m-%d"), 3), "Store": np.repeat(["Store A", "Store B", "Store C"], 52),
                       "Total Sales": np.round(r.uniform(20000, 90000, n), 2), "Footfall": r.integers(800, 5000, n), "Transactions": r.integers(300, 2000, n)})
    exp = {"Week": "event_date", "Store": "site_id", "Total Sales": "revenue", "Footfall": "activity_count", "Transactions": "activity_count"}
    return "weekly_store_sales.csv", df, exp


def subscriptions(seed=17):
    r = _rng(seed); n = 300
    df = pd.DataFrame({"Account ID": [f"AC{i:04d}" for i in range(n)], "Plan": r.choice(["Basic", "Pro", "Enterprise"], n), "MRR": r.choice([29.0, 99.0, 499.0], n),
                       "Seats": r.integers(1, 50, n), "Start Date": _dates(n, freq="1D").strftime("%Y-%m-%d"), "Status": r.choice(["Active", "Active", "Churned"], n)})
    exp = {"Account ID": "customer_id", "Plan": "segment", "MRR": "revenue", "Seats": "quantity", "Start Date": {"signup_date", "event_date"}, "Status": "status"}
    return "subscriptions.csv", df, exp


def indian_shop(seed=18):
    r = _rng(seed); n = N
    q = r.integers(1, 12, n); rt = r.choice([45.0, 120.0, 260.0, 999.0], n); dp = r.choice([0, 5, 10], n); net = np.round(q * rt * (1 - dp / 100), 2)
    df = pd.DataFrame({"Bill Date": _dates(n, freq="5h").strftime("%d.%m.%Y"), "Bill No.": [f"{x}" for x in r.integers(5000, 5400, n)], "Customer Mobile": [f"98{x:08d}" for x in r.integers(0, 10**8, n)],
                       "Item Qty": q, "MRP": rt, "Disc %": dp, "Net Amt": net, "Category": r.choice(["Grocery", "Personal Care", "Household"], n), "Counter": r.choice(["C1", "C2", "C3"], n)})
    exp = {"Bill Date": "event_date", "Bill No.": "order_id", "Customer Mobile": "personal", "Item Qty": "quantity", "MRP": "unit_price", "Disc %": "discount_pct",
           "Net Amt": "revenue", "Category": "product_group"}
    return "shop_bills.csv", df, exp


ALL = [superstore, online_retail, restaurant_pos, pharmacy_stock, purchase_orders, ecommerce_orders, clinic, wholesale_lines, salon, stock_ledger,
       hotel, marketing, customer_master, product_master, tally_register, weekly_store, subscriptions, indian_shop]


def cases():
    return [f() for f in ALL]

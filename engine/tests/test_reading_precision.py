"""Column reading: right meaning AND an honest confidence. Clear columns are not sent to the owner to check; unclear ones are.
All data is made up for the test."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_engine.understand.prepare import prepare
from alpha_engine.model.build import build_model
from alpha_engine.link.linker import find_links

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapping_report                                   # noqa: E402
import mapping_cases, mapping_holdout, mapping_blind    # noqa: E402

R = np.random.default_rng(3)


def _read(df: pd.DataFrame, name: str = "t.csv") -> dict:
    d = df.copy(); d.insert(0, "_row", range(2, len(d) + 2))
    p = prepare(d, name)
    return build_model({name: p}, [])["files"][name]["columns"], p


def test_clear_headers_are_confident_and_not_flagged():
    n = 300
    days = pd.date_range("2024-01-01", periods=n)
    df = pd.DataFrame({"order_id": [f"OR{i:05d}" for i in range(n)], "order_date": days.strftime("%Y-%m-%d"),
                       "ship_date": (days + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), "promised_date": (days + pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
                       "store_id": R.choice(["ST-NORTH", "ST-SOUTH", "WH-WEB"], n), "returned": R.choice(["Yes", "No"], n),
                       "gst_amount": np.round(R.uniform(5, 90, n), 2), "order_total": np.round(R.uniform(100, 900, n), 2)})
    cols, _ = _read(df, "orders.csv")
    for c in ("order_id", "ship_date", "promised_date", "store_id", "returned", "gst_amount", "order_total"):
        assert cols[c]["confidence"] >= 0.8, (c, cols[c])
        assert not cols[c]["needs_confirmation"], c
    assert cols["store_id"]["concept"] == "site_id" and cols["gst_amount"]["concept"] == "tax" and cols["returned"]["concept"] == "yes_no"


def test_vague_headers_are_still_flagged():
    n = 300
    df = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"), "Value": np.round(R.uniform(10, 500, n), 2),
                       "Amount": np.round(R.uniform(5, 200, n), 2), "Col7": R.integers(1, 50, n)})
    cols, _ = _read(df, "export.csv")
    assert cols["Value"]["needs_confirmation"] and cols["Col7"]["needs_confirmation"]
    assert cols["Amount"]["needs_confirmation"]                   # two loose amounts: which is the sale is the owner's call


def test_names_next_to_ids_list_prices_titles_types_and_dates():
    n = 120
    sup = pd.DataFrame({"supplier_id": [f"SP-{i:02d}" for i in range(12)] * 10, "supplier_name": [f"Supplier {i}" for i in range(12)] * 10,
                        "po_type": R.choice(["Regular", "Urgent"], n), "list_price": R.uniform(100, 200, n).round(2), "unit_price": R.uniform(80, 150, n).round(2),
                        "po_date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"), "qty_ordered": R.integers(1, 20, n)})
    cols, _ = _read(sup, "purchases.csv")
    assert cols["supplier_name"]["concept"] == "name_label"        # the name of the supplier, not a second supplier key
    assert cols["supplier_id"]["concept"] == "supplier_id"
    assert cols["list_price"]["concept"] == "list_price" and cols["unit_price"]["concept"] in ("unit_price", "unit_cost")
    assert cols["po_type"]["concept"] == "group"                   # a type of purchase order, not a customer segment
    staff = pd.DataFrame({"employee_id": [f"E{i:03d}" for i in range(40)], "join_date": pd.date_range("2020-01-01", periods=40, freq="MS").strftime("%Y-%m-%d"),
                          "exit_date": [None] * 30 + list(pd.date_range("2024-01-01", periods=10, freq="MS").strftime("%Y-%m-%d"))})
    cols, _ = _read(staff, "staff.csv")
    assert cols["join_date"]["concept"] == "signup_date" and cols["exit_date"]["concept"] == "end_date"
    rev = pd.DataFrame({"review_id": [f"RV{i:05d}" for i in range(n)], "review_date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
                        "review_title": R.choice(["Works well", "Bad battery", "Great value", "Stopped working"], n), "rating": R.integers(1, 6, n)})
    cols, _ = _read(rev, "reviews.csv")
    assert cols["review_title"]["concept"] == "free_text"


def test_id_column_with_a_stand_in_value_is_still_an_id():
    n = 2000
    cid = [f"C{x:05d}" for x in R.integers(1, 1500, n)]
    cid = [c if R.random() > 0.15 else "WALKIN" for c in cid]
    df = pd.DataFrame({"order_id": [f"O{i:06d}" for i in range(n)], "order_date": pd.date_range("2024-01-01", periods=n, freq="4h").strftime("%Y-%m-%d %H:%M"),
                       "customer_id": cid, "amount": R.uniform(10, 100, n).round(2)})
    cols, p = _read(df, "sales.csv")
    assert p.roles["customer_id"]["role"] == "id" and cols["customer_id"]["concept"] == "customer_id"


def test_a_column_holding_another_lists_codes_is_proposed_as_a_link():
    stores = pd.DataFrame({"store_id": ["ST-NORTH", "ST-SOUTH", "WH-WEB"], "city": ["A", "B", "C"]})
    cust = pd.DataFrame({"customer_id": [f"C{i:04d}" for i in range(200)], "home_store": R.choice(["ST-NORTH", "ST-SOUTH", "WH-WEB"], 200)})
    t = {}
    for name, df in (("stores.csv", stores), ("customers.csv", cust)):
        d = df.copy(); d.insert(0, "_row", range(2, len(d) + 2)); t[name] = prepare(d, name)
    links = [l for l in find_links(t) if l.child_col == "home_store"]
    assert links and links[0].parent_col == "store_id" and links[0].coverage == 1.0
    assert not any(l.child_col == "city" for l in find_links(t))  # same-looking words that are not codes never link


def test_few_columns_of_the_labelled_sets_go_to_the_owner():
    flagged = total = 0
    for mod in (mapping_cases, mapping_holdout, mapping_blind):
        for name, df, exp in mod.cases():
            d = df.copy(); d.insert(0, "_row", range(2, len(d) + 2))
            p = prepare(d, name)
            cols = build_model({name: p}, [])["files"][name]["columns"]
            for c in exp:
                total += 1
                flagged += bool(cols.get(c, {}).get("needs_confirmation"))
    assert flagged / total <= 0.12, f"{flagged}/{total} labelled columns sent to the owner to check"

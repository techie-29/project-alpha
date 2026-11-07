"""Data validation: a messy export with known problems planted in it; each check must find its problem, and a clean
file must pass. Runs through the real reader, so the file-structure checks are tested too."""
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_engine import pipeline

R = np.random.default_rng(42)


def _messy(n=1500):
    d = pd.date_range("2023-01-01", "2024-06-17", periods=n)
    d = d[(d < "2023-07-01") | (d >= "2023-08-01")]                       # July 2023 missing: a gap
    n = len(d)
    qty = R.integers(1, 6, n); price = R.choice([120.0, 250.0, 499.0, 999.0], n)
    disc = R.choice([0.0, 0.05, 0.1], n)
    sales = np.round(qty * price * (1 - disc), 2)
    profit = np.round(sales * R.uniform(0.05, 0.3, n), 2)
    df = pd.DataFrame({"Order ID": [f"SO-{i:05d}" for i in range(n)], "Order Date": d.strftime("%Y-%m-%d"),
                       "Customer ID": [f"C{x:03d}" for x in R.integers(1, 200, n)], "Product ID": [f"P{x:02d}" for x in R.integers(1, 40, n)],
                       "City": R.choice(["Mumbai", "Pune", "Delhi", "Bengaluru"], n), "Status": R.choice(["Delivered"] * 9 + ["Cancelled"], n),
                       "Quantity": qty, "Unit Price": price, "Discount %": disc, "Sales": sales.astype(object), "Profit": profit})
    df.loc[5:14, "Customer ID"] = None
    df.loc[20:22, "Profit"] = df.loc[20:22, "Sales"].astype(float) * 3          # profit above sale
    df.loc[30:31, "Unit Price"] = -50.0                                           # negative price
    df.loc[40:47, "Discount %"] = 5.0                                             # 5 instead of 0.05
    df.loc[50, "Sales"] = 950000.0; df.loc[50, "Profit"] = 1000.0                 # one extreme sale
    df.loc[60:61, "Order Date"] = "2031-03-01"                                    # dates in the future
    df.loc[70:74, "Order ID"] = "SO-00001"                                        # repeated order id
    df.loc[80:84, "Sales"] = "₹1,234.00"                                          # text in a number column
    df.loc[90:91, "Sales"] = "n.a."
    df.loc[100:130, "City"] = "Bengaluru."                                        # a second spelling
    df.loc[131:133, "City"] = "Bengaluuru"                                        # a rare misspelling
    df = pd.concat([df, df.iloc[[200, 201, 202]]], ignore_index=True)             # 3 exact copies
    total = {c: "" for c in df.columns}; total["Order ID"] = "Grand Total"; total["Sales"] = "123"
    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)
    return df


def _run(df, name="messy_sales.csv", title_lines=True):
    d = tempfile.mkdtemp()
    path = Path(d) / name
    text = df.to_csv(index=False)
    if title_lines:
        text = "Sales report\nExported 2024-06-18\n" + text
    path.write_text(text, encoding="utf-8")
    rep = pipeline.analyze("t", [{"name": name, "path": str(path)}], {}, d, None)
    f = rep["data_check"]["files"][0]
    return rep, {c["id"]: c for c in f["checks"]}, f


def test_each_planted_problem_is_found():
    rep, c, f = _run(_messy())
    assert len(c) == 27
    assert c["header_offset"]["status"] == "fixed"
    assert c["total_rows"]["status"] == "fixed"
    assert c["duplicate_rows"]["status"] == "fixed" and c["duplicate_rows"]["rows"] == 3
    assert c["missing_values"]["status"] in ("warn", "info") and "Customer ID" in c["missing_values"]["detail"]
    assert c["time_gaps"]["status"] == "warn" and "2023-07" in c["time_gaps"]["periods"]
    assert c["partial_periods"]["status"] == "warn"
    assert c["duplicate_ids"]["status"] == "warn" and c["duplicate_ids"]["rows"] >= 5
    assert c["text_in_numbers"]["status"] == "warn"                    # 'n.a.' is not a number
    assert any(p["status"] == "fixed" for p in c["text_in_numbers"].get("parts", [])) or c["text_in_numbers"]["detail"].count("read as numbers")
    assert c["dates_out_of_range"]["status"] == "warn" and c["dates_out_of_range"]["rows"] == 2
    assert c["group_variants"]["status"] == "warn" and "Bengaluru" in c["group_variants"]["detail"]
    assert c["mixed_scales"]["status"] in ("fixed", "warn") and c["mixed_scales"]["rows"] >= 8
    assert c["profit_above_sale"]["status"] == "fail" and c["profit_above_sale"]["rows"] >= 3
    assert c["negative_values"]["status"] == "fail"
    assert c["extreme_values"]["status"] == "warn"
    assert c["status_conflicts"]["status"] in ("pass", "warn")
    # every flagged check names real rows in the original file, and statuses add up
    assert c["profit_above_sale"]["examples"]["rows"] and all(isinstance(x, int) for x in c["profit_above_sale"]["examples"]["all_rows"])
    assert f["rows"]["flagged"] > 0 and f["rows"]["left_out"] > 0
    assert f["rows_in_file"] == sum(f["rows"].values())
    assert f["reconciliation"]["sales_in_file"] >= f["reconciliation"]["sales_counted"]


def test_clean_file_passes():
    n = 900
    d = pd.date_range("2024-01-01", "2024-06-30", periods=n)
    q = R.integers(1, 5, n); pr = R.choice([100.0, 200.0], n)
    df = pd.DataFrame({"Order ID": [f"O{i:05d}" for i in range(n)], "Order Date": d.strftime("%Y-%m-%d"), "Customer ID": [f"C{x:03d}" for x in R.integers(1, 90, n)],
                       "Quantity": q, "Unit Price": pr, "Sales": q * pr, "Region": R.choice(["North", "South"], n)})
    rep, c, f = _run(df, "clean_sales.csv", title_lines=False)
    bad = {k: v["status"] for k, v in c.items() if v["status"] in ("warn", "fail")}
    assert not bad, bad
    assert f["rows"]["ok"] == n and f["rows"]["flagged"] == 0


def test_codes_missing_from_the_linked_list_are_reported():
    from alpha_engine.understand.prepare import prepare
    from alpha_engine.model.build import build_model
    from alpha_engine.link.linker import find_links
    from alpha_engine.metrics.frame import build_frame
    from alpha_engine.validate import validate
    n = 3000
    q = R.integers(1, 5, n); pr = R.choice([10.0, 20.0], n)
    sales = pd.DataFrame({"_row": range(2, n + 2), "Order ID": [f"O{i}" for i in range(n)], "Order Date": pd.date_range("2024-01-01", periods=n, freq="2h").strftime("%Y-%m-%d"),
                          "Product ID": [f"P{x}" for x in R.integers(1, 120, n)], "Quantity": q, "Unit Price": pr, "Sales": q * pr})
    prods = pd.DataFrame({"_row": range(2, 102), "Product ID": [f"P{x}" for x in range(1, 101)], "Category": R.choice(["A", "B"], 100)})
    tables = {"sales.csv": prepare(sales, "sales.csv"), "products.csv": prepare(prods, "products.csv")}
    links = find_links(tables); m = build_model(tables, links)
    frames = {k: build_frame(p, m["files"][k]["columns"], m["files"][k]["file"], tables, links, m["files"]) for k, p in tables.items()}
    c = {x["id"]: x for x in validate(tables, frames, m, links)["files"][0]["checks"]}
    assert c["orphan_codes"]["status"] == "warn" and c["orphan_codes"]["rows"] > 0


def test_same_rows_in_two_uploads_are_reported():
    from alpha_engine.understand.prepare import prepare
    from alpha_engine.model.build import build_model
    from alpha_engine.metrics.frame import build_frame
    from alpha_engine.validate import validate
    df = _messy().iloc[:-1].reset_index(drop=True)
    df.insert(0, "_row", range(2, len(df) + 2))
    a, b = df.iloc[:800].reset_index(drop=True), df.iloc[600:].reset_index(drop=True)
    tables = {"jan_jun.csv": prepare(a, "jan_jun.csv"), "jun_dec.csv": prepare(b, "jun_dec.csv")}
    m = build_model(tables, [])
    frames = {k: build_frame(p, m["files"][k]["columns"], m["files"][k]["file"], tables, [], m["files"]) for k, p in tables.items()}
    files = validate(tables, frames, m, [])["files"]
    c = {x["id"]: x for x in files[0]["checks"]}
    assert c["overlapping_files"]["status"] == "warn" and c["overlapping_files"]["rows"] >= 150

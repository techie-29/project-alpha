"""Real-world exports: title lines, ';' separators, decimal commas, %, currency symbols, N/A, mixed case, header on row 3 in Excel, duplicates."""
import numpy as np
import pandas as pd
from alpha_engine.understand.reader import read_any
from alpha_engine.understand.prepare import prepare
from alpha_engine.model.build import build_model


def test_semicolon_export_with_title_lines_and_decimal_commas(tmp_path):
    p = tmp_path / "pos.csv"
    lines = ["POS export - Store 2;;;;;", "Generated 2025-07-01;;;;;", ";;;;;", "Receipt;Date / Time;Item Name;Qty;Line Total;Discount"]
    for i in range(300):
        lines.append(f"T{i};{(i % 28) + 1:02d}/03/2024 1{i % 9}:30;{['Tea', 'Bagel', 'Cake'][i % 3]};{1 + i % 3};€{(i % 7) + 2},50;{[0, 10, 20][i % 3]}%")
    lines.append("TOTAL;;;600;;")
    p.write_text("\n".join(lines), encoding="utf-8")
    df, notes = read_any(str(p))
    assert list(df.columns[:6]) == ["Receipt", "Date / Time", "Item Name", "Qty", "Line Total", "Discount"]
    assert any("';'" in n for n in notes) and any("above the header" in n for n in notes) and any("decimal comma" in n for n in notes)
    assert df["_row"].iloc[0] == 5                       # row numbers still match the original file
    P = prepare(df, "pos.csv")
    assert P.time_col == "Date / Time" and P.kind == "events" and len(P.df) == 300        # total row dropped, day-first dates
    m = build_model({"pos.csv": P}, [])
    c = {k: v["concept"] for k, v in m["files"]["pos.csv"]["columns"].items()}
    assert c["Line Total"] == "revenue" and c["Discount"] == "discount_pct" and c["Item Name"] == "product_id"
    assert m["files"]["pos.csv"]["columns"]["__currency__"]["constant"] == "EUR"
    assert abs(P.df["Line Total"].iloc[0] - 2.5) < 1e-9 and abs(P.df["Discount"].iloc[1] - 0.1) < 1e-9


def test_blanks_casing_and_duplicates(tmp_path):
    p = tmp_path / "inv.csv"
    rows = [{"invoice_no": f"I{i}", "plan": ["pro", "Pro", "PRO", "Basic"][i % 4], "amount_usd": f" {99 + i % 3}.00 ", "country": ["US", "N/A", "-", "DE"][i % 4]} for i in range(200)]
    df0 = pd.DataFrame(rows)
    df0 = pd.concat([df0, df0.iloc[:5]])
    df0.to_csv(p, index=False)
    df, notes = read_any(str(p))
    assert set(df["plan"].dropna().unique()) == {"Pro", "Basic"} or set(df["plan"].dropna().unique()) == {"pro", "Basic"}
    assert df["country"].isna().sum() == 100 and len(df) == 200 and any("exact copies" in n for n in notes)


def test_excel_with_header_on_row_three(tmp_path):
    p = tmp_path / "clinic.xlsx"
    body = pd.DataFrame({"Appt ID": [f"A{i}" for i in range(50)], "Appt Date": pd.date_range("2024-01-01", periods=50).strftime("%Y-%m-%d"), "Fee": ["₹1,200"] * 50})
    with pd.ExcelWriter(p) as xw:
        pd.DataFrame([["Clinic register"], ["exported"]]).to_excel(xw, sheet_name="R", header=False, index=False)
        body.to_excel(xw, sheet_name="R", startrow=2, index=False)
        pd.DataFrame({"x": [1]}).to_excel(xw, sheet_name="Notes", index=False)
    df, notes = read_any(str(p))
    assert list(df.columns[:3]) == ["Appt ID", "Appt Date", "Fee"] and len(df) == 50
    P = prepare(df, "clinic.xlsx")
    m = build_model({"clinic.xlsx": P}, [])
    assert m["files"]["clinic.xlsx"]["columns"]["Fee"]["concept"] == "revenue" and m["files"]["clinic.xlsx"]["columns"]["__currency__"]["constant"] == "INR"

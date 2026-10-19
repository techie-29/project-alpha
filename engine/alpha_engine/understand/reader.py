"""Read any CSV / Excel file into a DataFrame. Row numbers refer to the source file (header = row 1)."""
from __future__ import annotations
import pandas as pd


def read_any(path: str) -> tuple[pd.DataFrame, list[str]]:
    notes: list[str] = []
    p = str(path).lower()
    df = None
    if p.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            sheets = pd.read_excel(path, sheet_name=None)
            name, df = max(sheets.items(), key=lambda kv: len(kv[1]))
            if len(sheets) > 1:
                notes.append(f"Workbook has {len(sheets)} sheets; used the largest ('{name}').")
        except Exception:
            df = None  # some ".xls" files are really CSV text
    if df is None:
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(path, low_memory=False, encoding=enc)
                if enc != "utf-8-sig":
                    notes.append("File was not UTF-8; read as Latin-1.")
                break
            except UnicodeDecodeError:
                continue
    if df is None:
        raise ValueError("Could not read this file as CSV or Excel.")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    df["_row"] = df.index + 2  # source-file row number
    return df, notes

"""Read any CSV / Excel export into a clean DataFrame, the way real files arrive:
title lines above the header, ';' or tab separators, decimal commas, 'N/A' / '-' for blanks, mixed casing, duplicate rows.
Every fix is written into notes so the owner can see it. Row numbers (_row) refer to the original file."""
from __future__ import annotations
import csv
import io
import re
from collections import Counter
import pandas as pd

NA = ["", " ", "N/A", "n/a", "NA", "na", "#N/A", "-", "--", "—", "null", "NULL", "Null", "None", "none", "nan", "NaN", "?", "#VALUE!", "#DIV/0!"]
DEC_COMMA = re.compile(r"^[^\d\-]{0,4}-?\d{1,3}(\.\d{3})*,\d{1,4}[^\d]{0,4}$|^[^\d\-]{0,4}-?\d+,\d{1,4}[^\d]{0,4}$")
NUMERIC_CELL = re.compile(r"^[^\d\-A-Za-z]{0,3}-?[\d.,]+%?[^\dA-Za-z]{0,3}$")


def _decode(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def _sniff_delimiter(lines: list[str]) -> str:
    best, best_score = ",", -1.0
    for d in (",", ";", "\t", "|"):
        counts = [len(next(csv.reader([l], delimiter=d))) for l in lines if l.strip()]
        if not counts:
            continue
        mode, freq = Counter(counts).most_common(1)[0]
        if mode < 2:
            continue
        score = freq / len(counts) + 0.01 * mode
        if score > best_score:
            best, best_score = d, score
    return best


def _is_texty(cell: str) -> bool:
    c = cell.strip()
    return bool(c) and not NUMERIC_CELL.match(c) and not re.match(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", c)


def _header_index(rows: list[list[str]]) -> int:
    """The header is the first row that is about as wide as the data, mostly text, and followed by rows of the same width."""
    widths = [sum(1 for c in r if str(c).strip()) for r in rows]
    if not widths:
        return 0
    full = Counter(w for w in widths if w > 0).most_common(1)[0][0]
    full = max(full, max(widths) if max(widths) <= full * 1.2 else full)
    for i, r in enumerate(rows[:30]):
        cells = [str(c) for c in r if str(c).strip()]
        if len(cells) >= max(2, 0.6 * full) and sum(_is_texty(c) for c in cells) >= 0.6 * len(cells):
            nxt = widths[i + 1: i + 6]
            if nxt and sum(1 for w in nxt if w >= 0.5 * full) >= 0.6 * len(nxt):
                return i
    return 0


def _fix_frame(df: pd.DataFrame, notes: list[str], skipped: int) -> pd.DataFrame:
    # names: strip, fill blanks, make unique
    cols, seen = [], Counter()
    for i, c in enumerate(df.columns):
        name = str(c).strip()
        if not name or name.lower().startswith("unnamed:") or name.lower() == "nan":
            name = f"column_{i + 1}"
        seen[name] += 1
        cols.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    df.columns = cols
    df = df.dropna(how="all")
    empty = [c for c in df.columns if df[c].isna().all()]
    if empty:
        df = df.drop(columns=empty)
        notes.append(f"Dropped {len(empty)} empty column(s).")
    df["_row"] = df.index + 2 + skipped
    df = df.reset_index(drop=True)
    # text cells: trim; decimal commas; unify casing of category values
    for c in [c for c in df.columns if c != "_row" and (df[c].dtype == object or pd.api.types.is_string_dtype(df[c]))]:
        s = df[c]
        st = s.dropna().astype(str).str.strip()
        if len(st) == 0:
            continue
        df[c] = s.where(s.isna(), s.astype(str).str.strip()).replace("", pd.NA)
        sample = st.sample(min(len(st), 2000), random_state=0)
        if sample.str.match(DEC_COMMA).mean() >= 0.8:
            df[c] = df[c].where(df[c].isna(), df[c].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
            notes.append(f"'{c}' uses a decimal comma (e.g. 3,90); read as a decimal point.")
            continue
        nu = st.nunique()
        if 1 < nu <= 300 and nu < 0.5 * len(st):
            low = st.str.casefold()
            if low.nunique() < nu:
                canon = st.groupby(low).agg(lambda x: x.value_counts().index[0])
                df[c] = df[c].where(df[c].isna(), df[c].astype(str).str.casefold().map(canon))
                notes.append(f"'{c}': values that differ only in capitals (e.g. 'pro' / 'Pro' / 'PRO') were treated as the same.")
    # exact duplicate rows
    data_cols = [c for c in df.columns if c != "_row"]
    dup = df.duplicated(subset=data_cols)
    if dup.any() and dup.mean() < 0.05:
        notes.append(f"Removed {int(dup.sum()):,} row(s) that were exact copies of another row (every column identical).")
        df = df[~dup].reset_index(drop=True)
    elif dup.any():
        notes.append(f"{int(dup.sum()):,} rows ({dup.mean():.0%}) are exact copies of other rows. They were kept, because that many copies may be real repeated events.")
    return df


def _read_text(path: str, notes: list[str]) -> pd.DataFrame:
    raw = open(path, "rb").read()
    text, enc = _decode(raw)
    if enc != "utf-8-sig":
        notes.append(f"File was not UTF-8; read as {enc}.")
    lines = text.splitlines()
    head = [l for l in lines[:200]]
    delim = _sniff_delimiter([l for l in head if l.strip()][:60])
    if delim != ",":
        notes.append({";": "Columns are separated by ';'.", "\t": "Columns are separated by tabs.", "|": "Columns are separated by '|'."}[delim])
    rows = list(csv.reader(head[:40], delimiter=delim))
    h = _header_index(rows)
    skipped = sum(1 for l in lines[:h])
    if h:
        notes.append(f"Skipped {h} line(s) above the header (titles or notes).")
    df = pd.read_csv(io.StringIO(text), sep=delim, skiprows=h, na_values=NA, keep_default_na=True, low_memory=False,
                     skip_blank_lines=False, on_bad_lines="warn", dtype=str if False else None, engine="c")
    return _fix_frame(df, notes, skipped - h + h)


def _read_excel(path: str, notes: list[str]) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, header=None, na_values=NA)
    best = None
    for name, raw in sheets.items():
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        if raw.empty:
            continue
        rows = raw.head(40).astype(object).where(raw.head(40).notna(), "").astype(str).values.tolist()
        h = _header_index(rows)
        body = raw.iloc[h + 1:]
        if best is None or len(body) > best[2]:
            best = (name, raw, len(body), h)
    if best is None:
        raise ValueError("The workbook has no data.")
    name, raw, _, h = best
    if len(sheets) > 1:
        notes.append(f"Workbook has {len(sheets)} sheets; used '{name}', the one with the most data.")
    if h:
        notes.append(f"Skipped {h} line(s) above the header (titles or notes).")
    header = [str(x) if pd.notna(x) else "" for x in raw.iloc[h].tolist()]
    df = raw.iloc[h + 1:].copy()
    df.columns = header
    first_row = int(raw.index[h + 1]) if len(raw) > h + 1 else 0
    df.index = df.index - first_row + 0
    df = df.infer_objects()
    out = _fix_frame(df.reset_index(drop=True), notes, first_row - 0)
    return out


def read_any(path: str) -> tuple[pd.DataFrame, list[str]]:
    notes: list[str] = []
    p = str(path).lower()
    df = None
    if p.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            df = _read_excel(path, notes)
        except ValueError:
            raise
        except Exception:
            df = None                       # some ".xls" files are really CSV text
    if df is None:
        df = _read_text(path, notes)
    if df is None or df.empty:
        raise ValueError("Could not read any rows from this file.")
    return df, notes

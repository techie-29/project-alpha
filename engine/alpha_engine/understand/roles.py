"""Stage 1a: give every column a role (time, measure, category, id, text) from header AND values. Values get the final say."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd

ID_HINT = re.compile(r"(^|[_\s])(id|code|no|num|number|zip|postal|pin|phone|sku|key|uuid)($|[_\s])", re.I)
DATE_SHAPE = re.compile(r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})|([A-Za-z]{3,9}\.? \d{1,2},? \d{4})|(\d{1,2} [A-Za-z]{3,9}\.? \d{4})")
CUR = re.compile(r"[\$€£₹,\s%]")


def clean_numeric(s: pd.Series) -> pd.Series | None:
    """Turn '$1,234.50' / '12%' style text into numbers, if almost all values allow it."""
    if s.dtype != object:
        return None
    t = s.dropna().astype(str)
    if t.empty:
        return None
    conv = pd.to_numeric(t.str.replace(CUR, "", regex=True), errors="coerce")
    if conv.notna().mean() >= 0.95:
        return pd.to_numeric(s.astype(str).str.replace(CUR, "", regex=True), errors="coerce")
    return None


def infer_date_order(sample: pd.Series) -> str:
    """'iso' | 'day-first' | 'month-first' | 'ambiguous->day-first' (stated in the report)."""
    vals = sample.dropna().astype(str).head(2000)
    iso = vals.str.match(r"^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}")
    if iso.mean() > 0.9:
        return "iso"
    parts = vals.str.extract(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.]\d{2,4}").dropna().astype(int)
    if len(parts):
        if (parts[0] > 12).any():
            return "day-first"
        if (parts[1] > 12).any():
            return "month-first"
    return "ambiguous->day-first"


def parse_dates(s: pd.Series, order: str) -> pd.Series:
    if np.issubdtype(s.dtype, np.datetime64):
        return s
    if order == "iso":
        out = pd.to_datetime(s, errors="coerce", format="mixed")
    else:
        out = pd.to_datetime(s, errors="coerce", dayfirst=(order != "month-first"), format="mixed")
    return out


def looks_like_date(s: pd.Series) -> bool:
    if np.issubdtype(s.dtype, np.datetime64):
        return True
    if s.dtype != object:
        return False
    v = s.dropna().astype(str).head(500)
    return len(v) > 0 and v.str.contains(DATE_SHAPE).mean() > 0.9


def profile_columns(df: pd.DataFrame) -> dict[str, dict]:
    n = len(df)
    roles: dict[str, dict] = {}
    for c in df.columns:
        if c == "_row":
            continue
        s = df[c]
        nn = int(s.notna().sum())
        info = {"role": "empty", "non_null": nn}
        if nn == 0:
            roles[c] = info
            continue
        nu = int(s.nunique(dropna=True))
        info["unique"] = nu
        hint_id = bool(ID_HINT.search(c))
        if looks_like_date(s):
            order = infer_date_order(s) if s.dtype == object else "native"
            parsed = parse_dates(s, order)
            if parsed.notna().mean() > 0.9:
                info.update(role="time", date_order=order)
                roles[c] = info
                continue
        num = s if pd.api.types.is_numeric_dtype(s) and s.dtype != bool else clean_numeric(s)
        if s.dtype == bool or (s.dtype == object and set(s.dropna().astype(str).str.lower().unique()) <= {"true", "false"}):
            info.update(role="category")
        elif num is not None:
            is_int = bool((num.dropna() % 1 == 0).all())
            if hint_id or (is_int and nu >= 0.9 * nn and nu > 50 and not re.search(r"(sales|amount|price|cost|revenue|profit|qty|quantity)", c, re.I)):
                info.update(role="id")
            else:
                info.update(role="measure", cleaned=(s.dtype == object))
        else:
            if nu <= max(60, 0.002 * n):
                info.update(role="category")
            elif hint_id:
                info.update(role="id")
            elif nu <= 500 and nu <= 0.05 * nn:
                info.update(role="category", many_values=True)
            elif nu >= 0.5 * nn and s.astype(str).str.len().median() <= 20:
                info.update(role="id")
            else:
                info.update(role="text")
        roles[c] = info
    return roles

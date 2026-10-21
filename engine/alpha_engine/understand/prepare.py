"""Stage 1c: turn understood columns into clean, trustworthy analysis material.

Produces a `Prepared` object: a time axis, the rows that count, a list of measures to watch and the
columns to slice by. Every decision is written to `notes` in plain language so the report can show it.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from .roles import (profile_columns, parse_dates, clean_numeric, apply_owner_confirmations,
                    MONEY, COUNT, PCT, RATING)

TOTAL_ROW = re.compile(r"^\s*(grand\s+|sub\s*)?total[s]?\s*:?\s*$|^\s*(sum|average|mean)\s*:?\s*$", re.I)
PROBLEM_VALUE = re.compile(r"cancel|return|refund|fail|void|reject|declin|chargeback|abandon|no.?show|missed|did not attend|^dna$|absent|churn|expired|lapsed|overdue|unpaid|dispute|bounced|undeliver|lost", re.I)
STATUS_HEAD = re.compile(r"order[_\s]?status|^status$|transaction[_\s]?status|^state$", re.I)
PRESENCE_HEAD = re.compile(r"return|refund|cancel", re.I)
SUM_HEAD = re.compile(r"(sales|revenue|amount|cost|profit|qty|quantity|units|discount_amount|tax|shipping|fee|points|spend|income|expense|charge|payment|total)", re.I)
MEAN_HEAD = re.compile(r"(pct|percent|percentage|margin|rate|ratio|rating|score|age|days|price|lifetime|count|acquisition|average|avg|per_)", re.I)
MONEY_PRIORITY = ["net_sales", "net_revenue", "revenue", "total_sales", "sales_amount", "sales", "total_amount", "amount", "gross_sales", "total"]
MIN_SLICE_ROWS = 30          # hand-set statistical minimum (documented limit)
MIN_CURRENCY_SHARE = 0.02


@dataclass
class Measure:
    name: str
    col: str | None          # source column (None for row counts / rates)
    agg: str                 # 'sum' | 'mean' | 'count' | 'rate'
    scope: str               # 'ok' (rows that count) | 'all'
    kind: str                # 'money' | 'count' | 'rate' | 'other'
    currency: str | None = None
    flag_col: str | None = None   # for rates: boolean column in df


@dataclass
class Prepared:
    name: str
    df: pd.DataFrame
    roles: dict
    kind: str                         # events | periodic | reference | summary | no_time
    time_col: str | None = None
    ok: pd.Series | None = None
    measures: list[Measure] = field(default_factory=list)
    slices: list[str] = field(default_factory=list)
    money_col: str | None = None
    currency_col: str | None = None
    currencies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    synthetic_time: bool = False
    sources: list[str] = field(default_factory=list)   # files this view was built from


def _drop_total_rows(df: pd.DataFrame, notes: list[str]) -> pd.DataFrame:
    text_cols = [c for c in df.columns if c != "_row" and not pd.api.types.is_numeric_dtype(df[c])]
    if not text_cols:
        return df
    hit = pd.Series(False, index=df.index)
    for c in text_cols[:8]:
        hit |= df[c].astype(str).str.match(TOTAL_ROW).fillna(False)
    if hit.any() and hit.sum() <= max(3, int(0.01 * len(df))):
        notes.append(f"Left out {int(hit.sum())} total/summary row(s) (source rows {', '.join(map(str, df.loc[hit, '_row'].head(5)))}) so nothing is counted twice.")
        return df[~hit].reset_index(drop=True)
    return df


def _build_time(df: pd.DataFrame, roles: dict, confirmed: dict, p: Prepared) -> None:
    time_cols = [c for c, i in roles.items() if i["role"] == "time"]
    if time_cols:
        # prefer a header with 'date', then the most distinct values
        time_cols.sort(key=lambda c: (("date" not in c.lower()), -roles[c].get("unique", 0)))
        c = confirmed.get("__time_col__") if confirmed.get("__time_col__") in time_cols else time_cols[0]
        info = roles[c]
        t = parse_dates(df[c], info.get("date_order", "native"))
        bad = int(t.isna().sum() - df[c].isna().sum())
        p.time_col, df["_t"] = c, t
        if info.get("date_order") == "ambiguous->day-first":
            p.warnings.append(f"Dates in '{c}' could be day-first or month-first; read as day-first. Please check.")
        if bad > 0:
            p.warnings.append(f"{bad:,} value(s) in '{c}' could not be read as dates; those rows are left out of time analysis.")
        p.notes.append(f"Time axis: '{c}' ({info.get('date_order', 'native')} dates), {t.min():%d %b %Y} to {t.max():%d %b %Y}.")
        return
    # build a date from year / month / day columns
    parts = {i["period_part"]: c for c, i in roles.items() if i.get("period_part") and i["role"] == "category"}
    if "year" in parts or "yr" in parts:
        y = df[parts.get("year") or parts["yr"]]
        m = df[parts["month"]] if "month" in parts else 1
        d = df[parts["day"]] if "day" in parts else 1
        t = pd.to_datetime(pd.DataFrame({"year": y, "month": m, "day": d}), errors="coerce")
        if t.notna().mean() > 0.9:
            df["_t"], p.time_col = t, "+".join(parts.values())
            p.notes.append(f"No date column; built a date from {', '.join(parts.values())}.")
            return
    if confirmed.get("__rows_in_time_order__"):
        n = len(df)
        block = max(1, n // 100)
        df["_t"] = pd.Timestamp("2000-01-01") + pd.to_timedelta(np.arange(n) // block, unit="D")
        p.time_col, p.synthetic_time = "(row order)", True
        p.warnings.append("No date column: the owner said rows are in time order, so row position is used as time. Results are 'by row order', not by date.")


def _status_logic(df: pd.DataFrame, roles: dict, p: Prepared) -> None:
    """Which rows count toward money, and which problem-rates to watch."""
    excl = pd.Series(False, index=df.index)
    rate_cols: list[tuple[str, str, str]] = []   # (source col, value label, flag col)
    status_cols = [c for c, i in roles.items() if i["role"] in ("category", "flag")]
    primary = [c for c in status_cols if STATUS_HEAD.search(c)]
    for c in status_cols:
        info, s = roles[c], df[c]
        if info["role"] == "flag" and info.get("presence") and PRESENCE_HEAD.search(c):
            f = s.notna()
            fc = f"__rate__{c}"
            df[fc] = f
            rate_cols.append((c, "yes", fc))
            if not primary:
                excl |= f
            continue
        if info["role"] != "category" or info.get("unique", 99) > 15 or not re.search(r"status|state|outcome|result", c, re.I):
            continue
        for v in s.dropna().unique():
            if PROBLEM_VALUE.search(str(v)):
                fc = f"__rate__{c}={v}"
                df[fc] = (s == v)
                rate_cols.append((c, str(v), fc))
                if c in primary:
                    excl |= (s == v)
    qty = [c for c, i in roles.items() if i["role"] == "measure" and re.search(r"qty|quantity|units", c, re.I)]
    for c in qty:
        neg = pd.to_numeric(df[c], errors="coerce") < 0
        if neg.any():
            excl |= neg
            p.notes.append(f"Left out {int(neg.sum()):,} row(s) with negative '{c}'.")
    p.ok = ~excl
    if excl.any():
        names = ", ".join(sorted({c for c, _, _ in rate_cols if c in primary or PRESENCE_HEAD.search(c)})) or "status"
        p.notes.append(f"{int(excl.sum()):,} of {len(df):,} rows ({excl.mean():.1%}) are cancelled/returned/failed; they are left out of money and averages but still counted in problem rates (from {names}).")
    # consistency note: problem in a secondary status column on an otherwise fine row
    for c, v, fc in rate_cols:
        if c not in primary and not PRESENCE_HEAD.search(c) and re.search(r"payment", c, re.I):
            k = int((df[fc] & p.ok).sum())
            if k:
                p.warnings.append(f"{k:,} row(s) show '{v}' in {c} although the order status says they count. Left in; worth checking at the source.")
    keep = [(c, v, fc) for c, v, fc in rate_cols if MIN_SLICE_ROWS <= df[fc].sum() < len(df)]
    p._rate_cols = keep  # type: ignore[attr-defined]


def _currency(df: pd.DataFrame, roles: dict, p: Prepared) -> None:
    cands = [c for c, i in roles.items() if i["role"] == "category" and re.search(r"curr", c, re.I) and i.get("unique", 0) >= 1]
    if not cands:
        return
    c = cands[0]
    share = df[c].value_counts(normalize=True)
    keep = [k for k, v in share.items() if v >= MIN_CURRENCY_SHARE and (df[c] == k).sum() >= MIN_SLICE_ROWS]
    p.currency_col, p.currencies = c, [str(k) for k in keep]
    if len(share) > 1:
        small = [str(k) for k in share.index if k not in keep]
        p.notes.append(f"Amounts are in {len(share)} currencies ({', '.join(map(str, share.index[:8]))}). Money is analysed per currency and never added across currencies.")
        if small:
            p.warnings.append(f"Currencies with under {MIN_CURRENCY_SHARE:.0%} of rows ({', '.join(small)}) are not analysed as money.")


def _measures(df: pd.DataFrame, roles: dict, p: Prepared) -> None:
    p.measures = []
    money_cols: list[str] = []
    for c, i in roles.items():
        if i["role"] != "measure":
            continue
        num = df[c] if pd.api.types.is_numeric_dtype(df[c]) else clean_numeric(df[c])
        df[c] = num
        mean_like = bool(MEAN_HEAD.search(c)) and not re.search(r"discount_amount|tax_amount|shipping_cost", c, re.I)
        agg = "mean" if mean_like else ("sum" if SUM_HEAD.search(c) else "mean")
        is_money = agg == "sum" and bool(MONEY.search(c))
        if is_money and p.currency_col and len(p.currencies) > 1:
            for cur in p.currencies:
                p.measures.append(Measure(f"{c} [{cur}]", c, "sum", "ok", "money", cur))
        else:
            p.measures.append(Measure(c, c, agg, "ok", "money" if is_money else "other"))
        if is_money:
            money_cols.append(c)
    if p.kind == "events":
        p.measures.append(Measure("rows", None, "count", "ok", "count"))
    for src, val, fc in getattr(p, "_rate_cols", []):
        label = f"{src}" if val == "yes" else f"{src} = {val}"
        p.measures.append(Measure(f"rate of {label}", None, "rate", "all", "rate", flag_col=fc))
    for pr in MONEY_PRIORITY:
        hit = next((c for c in money_cols if c.lower() == pr), None) or next((c for c in money_cols if pr in c.lower()), None)
        if hit:
            p.money_col = hit
            break
    p.money_col = p.money_col or (money_cols[0] if money_cols else None)


def prepare(df: pd.DataFrame, name: str = "file", confirmed: dict | None = None, known_roles: dict | None = None) -> Prepared:
    """known_roles: column types already worked out (e.g. for a linked view built from files already read); only new
    columns are profiled again."""
    confirmed = confirmed or {}
    p = Prepared(name=name, df=df, roles={}, kind="no_time")
    df = _drop_total_rows(df.copy(), p.notes) if not known_roles else df.copy()
    p.df = df
    if known_roles:
        new = [c for c in df.columns if c not in known_roles and c != "_row"]
        prof = profile_columns(df[new]) if new else {}
        base = {c: {k: (list(v) if isinstance(v, list) else v) for k, v in known_roles[c].items()} for c in df.columns if c in known_roles}
        prof = {**base, **prof}
    else:
        prof = profile_columns(df)
    roles = apply_owner_confirmations(prof, {k: v for k, v in confirmed.items() if not k.startswith("__")})
    p.roles = roles
    if len(df) <= 3 and not any(i["role"] == "time" for i in roles.values()):
        p.kind = "summary"
        p.notes.append("Looks like a summary of another file (very few rows, no dates). Not analysed; used only for cross-checking totals.")
        return p
    _build_time(df, roles, confirmed, p)
    if p.time_col is None:
        p.kind = "reference" if len(df) > 3 else "summary"
        p.notes.append("No dates in this file. It is used as extra detail for files it links to; on its own only a snapshot view is possible (no 'what changed').")
    else:
        dates = df["_t"].dropna()
        day = dates.dt.normalize()
        has_clock = bool((dates != day).mean() > 0.05)                    # times of day present: judge by calendar day
        p.kind = "periodic" if (day.nunique() if has_clock else dates.nunique()) >= 0.9 * len(dates) else "events"
        if p.kind == "periodic":
            p.notes.append("About one row per date: each row is treated as a period total, so row counts are not a measure.")
    _status_logic(df, roles, p)
    for c in [c for c in df.columns if c.startswith("__ok_")]:      # a parent record (e.g. the order) that does not count
        p.ok &= df[c].fillna(True).astype(bool)
    _currency(df, roles, p)
    _measures(df, roles, p)
    cat = [c for c, i in roles.items() if i["role"] in ("category", "flag") and not i.get("period_part") and 2 <= i.get("unique", 0) <= 500
           and not c.startswith("__") and not (i["role"] == "flag" and i.get("presence"))]
    cat += [c for c, i in roles.items() if i["role"] == "measure" and "category" in i.get("secondary", []) and i.get("unique", 99) <= 12]
    p.slices = list(dict.fromkeys(cat))
    return p

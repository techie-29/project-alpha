"""What the AI is allowed to see about an upload. Never raw rows, never personal columns, never free text.

raw_profile  - the plain shape of each file: column names, kind of values, ranges, a few category values. Used by the
               full-AI brain, which decides meanings, checks and analyses itself.
fact_sheet   - raw_profile plus what the engine already worked out: column meanings, the metrics this file can
               calculate (with formulas) and those it cannot (and why), headline numbers and the data-check summary.
               Used by the metric + AI brain."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from .understand.roles import PII_HEAD
from .model.infer import is_pii
from .model.concepts import CONCEPTS

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
PHONE = re.compile(r"^\+?[\d\s\-()]{8,15}$")
SAFE_VALUE = re.compile(r"^[\w .,&/()+%'#:-]{1,40}$")


def personal(col: str, s: pd.Series) -> bool:
    """Privacy guard (code, not AI): header names a person or contact detail, or the values look like emails / phone numbers."""
    if is_pii(col) or PII_HEAD.search(str(col)):
        return True
    v = s.dropna().astype(str).head(200)
    if len(v) and (v.str.match(EMAIL).mean() > 0.5 or (v.str.match(PHONE).mean() > 0.8 and v.str.replace(r"\D", "", regex=True).str.len().median() >= 10)):
        return True
    return False


def _safe_values(s: pd.Series, k: int = 8) -> list[str]:
    v = s.dropna().alpha.strip_str()
    if v.nunique() > 60:
        return []
    return [x for x in v.value_counts().index[:k] if SAFE_VALUE.match(x)]


def column_profile(col: str, s: pd.Series) -> dict:
    nn = int(s.notna().sum())
    out = {"name": col, "filled": round(nn / max(len(s), 1), 3), "distinct": int(s.nunique(dropna=True))}
    if pd.api.types.is_datetime64_any_dtype(s):
        d = s.dropna()
        out.update(kind="date", first=str(d.min().date()) if len(d) else None, last=str(d.max().date()) if len(d) else None)
    elif pd.api.types.is_numeric_dtype(s) and s.dtype != bool:
        v = s.dropna().astype(float)
        if len(v):
            out.update(kind="number", min=float(v.min()), median=float(v.median()), max=float(v.max()), whole_numbers=bool((v % 1 == 0).mean() > 0.98),
                       negative_share=round(float((v < 0).mean()), 4), zero_share=round(float((v == 0).mean()), 4))
        else:
            out["kind"] = "number"
    else:
        v = s.dropna().astype(str)
        out.update(kind="text", avg_length=round(float(v.str.len().mean()), 1) if len(v) else 0, examples=_safe_values(s))
    return out


def raw_profile(tables: dict) -> list[dict]:
    files = []
    for name, p in tables.items():
        df = p.df
        cols, withheld = [], []
        for c in df.columns:
            if str(c).startswith("_") and c != "_t":
                continue
            if c == "_t":
                continue
            if personal(str(c), df[c]):
                withheld.append(str(c)); continue
            cols.append(column_profile(str(c), df[c]))
        files.append({"file": name, "rows": int(len(df)), "columns": cols, "withheld_personal_columns": withheld,
                      "notes_from_reading": [n for n in p.notes if isinstance(n, str)][:12]})
    return files


def metrics_menu(F) -> dict:
    """Which catalogue metrics this file can calculate, and what is missing for the others."""
    from .metrics.catalogue import CATALOGUE, available
    have = {m.id: m for m in available(F)}
    avail = [{"id": m.id, "label": m.label, "formula": m.how, "area": m.area, "format": m.fmt, "good_when": {1: "higher", -1: "lower"}.get(m.polarity, "neither")}
             for m in have.values() if m.tier != "input"]
    blocked = []
    for m in CATALOGUE:
        if m.id in have or m.tier != "core" or F.role not in m.roles:
            continue
        miss = [n for n in m.needs if not F.has(n)]
        if miss:
            blocked.append({"id": m.id, "label": m.label, "needs": [CONCEPTS[n].label if n in CONCEPTS else n.strip("_").replace("_", " ") for n in miss]})
    return {"available": avail, "blocked": blocked[:40]}


def fact_sheet(report: dict, frames: dict, model: dict, tables: dict) -> dict:
    files = []
    raw = {f["file"]: f for f in raw_profile(tables)}
    for name, F in frames.items():
        fm = model["files"].get(name, {})
        cols = []
        for c in raw.get(name, {}).get("columns", []):
            v = fm.get("columns", {}).get(c["name"])
            canon = next((k for k, src in F.canon.items() if src == c["name"]), None)
            item = dict(c)
            if v:
                item["means"] = v["label"]
                item["sure"] = v["confidence"]
            if canon:
                item["use_as"] = canon                      # the name to use in requests
            cols.append(item)
        groups = [{"column": c, "distinct": int(F.df[c].nunique())} for c in sorted({c for cs in F.groups.values() for c in cs}) if c in F.df.columns
                  and 2 <= F.df[c].nunique() <= 200 and not personal(c, F.df[c])]
        span = None
        if F.has_time and F.df["_t"].notna().any():
            t = F.df["_t"].dropna()
            days = (t.max() - t.min()).days
            span = {"from": str(t.min().date()), "to": str(t.max().date()), "days": int(days), "suggested_grain": "day" if days <= 120 else ("week" if days <= 365 else "month")}
        files.append({"file": name, "kind": F.role, "entity": F.entity, "rows": int(len(F.df)), "currency": F.currency, "columns": cols,
                      "groups_to_split_by": groups, "time": span, "metrics": metrics_menu(F),
                      "withheld_personal_columns": raw.get(name, {}).get("withheld_personal_columns", [])})
    dc = report.get("data_check") or {}
    problems = [{"file": f["file"], "check": c["title"], "status": c["status"], "rows": c.get("rows"), "detail": c["detail"][:300]}
                for f in dc.get("files", []) for c in f["checks"] if c["status"] in ("warn", "fail")]
    tiles = [{"label": t["label"], "value": t["value"], "unit": t.get("unit"), "format": t.get("fmt"),
              "change_vs_last_year": (t.get("vs_last_year") or {}).get("change"), "last_12_months_change": (t.get("last_12_months") or {}).get("change")}
             for t in (report.get("overview") or {}).get("tiles", [])]
    return {"files": files, "headline_numbers": tiles, "data_problems": problems[:30], "data_check_summary": dc.get("headline")}


def numbers_of(obj) -> list:
    """Every number in a structure (for 'headline numbers anyone may quote')."""
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += numbers_of(v)
    elif isinstance(obj, list):
        for v in obj:
            out += numbers_of(v)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool) and np.isfinite(obj):
        out.append(float(obj))
    return out

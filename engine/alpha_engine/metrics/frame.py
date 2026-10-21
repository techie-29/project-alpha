"""A standard analysis frame per file: columns renamed by business concept, derived values added, master-list attributes
looked up through confirmed links. Every metric and chart is computed from these frames, so they work for any business."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from ..model.concepts import CONCEPTS

NUMERIC_CANON = ["revenue", "gross_revenue", "cost", "expense", "profit", "discount", "discount_pct", "tax", "unit_price", "unit_cost", "money_other",
                 "quantity", "stock_level", "reorder_level", "margin_pct", "rating", "duration", "promised_duration", "age", "points", "activity_count", "percent"]
KEY_CANON = ["order_id", "customer_id", "product_id", "employee_id", "supplier_id", "site_id"]
MONEY = {c for c in NUMERIC_CANON if CONCEPTS[c].money}


@dataclass
class Frame:
    name: str
    role: str
    entity: str | None
    df: pd.DataFrame                      # canonical columns + original group columns + _t, _ok, _cur
    has_time: bool
    canon: dict[str, str] = field(default_factory=dict)       # canonical name -> source column
    groups: dict[str, list[str]] = field(default_factory=dict)  # group concept -> columns (original names)
    extra_numbers: list[tuple[str, str]] = field(default_factory=list)   # (column, concept) not used canonically
    currency: str | None = None           # main currency of money values (None = unknown / single)
    currencies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status_flags: list[tuple[str, str, str]] = field(default_factory=list)   # (status column, value, flag column)

    def has(self, *names) -> bool:
        return all(n in self.df.columns and self.df[n].notna().any() for n in names)


def _primary(cols: dict, concept: str) -> str | None:
    hits = [(v["confidence"], c) for c, v in cols.items() if v["concept"] == concept]
    return max(hits)[1] if hits else None


def build_frame(p, model_cols: dict, file_info: dict, tables: dict | None = None, links: list | None = None, models: dict | None = None) -> Frame:
    src = p.df
    out = pd.DataFrame(index=src.index)
    has_time = "_t" in src.columns and src["_t"].notna().any()
    if has_time:
        out["_t"] = pd.to_datetime(src["_t"], errors="coerce")
    out["_ok"] = p.ok.values if p.ok is not None else True
    out["_row"] = src["_row"].values if "_row" in src.columns else np.arange(2, len(src) + 2)
    F = Frame(p.name, file_info.get("role", "other"), file_info.get("entity"), out, has_time)
    concept_cols = dict(model_cols)
    # columns borrowed from parents in a linked view carry their parent's concepts
    for s in (p.sources or [])[1:]:
        for c, v in ((models or {}).get(s, {}).get("columns", {}) or {}).items():
            if c in src.columns and c not in concept_cols:
                concept_cols[c] = v
    for canon in NUMERIC_CANON + KEY_CANON:
        c = _primary(concept_cols, canon)
        if c is not None and c in src.columns:
            vals = src[c]
            out[canon] = pd.to_numeric(vals, errors="coerce") if canon in NUMERIC_CANON else vals.astype("string").str.strip()
            F.canon[canon] = c
    used = set(F.canon.values())
    for c, v in concept_cols.items():
        con = CONCEPTS[v["concept"]]
        if c not in src.columns:
            continue
        if con.kind == "group" and v["concept"] not in ("currency",):
            F.groups.setdefault(v["concept"], []).append(c)
            out[c] = src[c].astype("string").str.strip()
        elif con.kind == "number" and c not in used:
            F.extra_numbers.append((c, v["concept"]))
            out[c] = pd.to_numeric(src[c], errors="coerce")
        elif con.kind == "key" and c not in used:
            F.groups.setdefault(v["concept"], []).append(c)
            out[c] = src[c].astype("string").str.strip()
    cur_col = _primary(concept_cols, "currency")
    if cur_col is not None:
        cv = concept_cols[cur_col]
        if cv.get("constant"):
            out["_cur"] = cv["constant"]
        elif cur_col in src.columns:
            out["_cur"] = src[cur_col].astype("string").str.strip().str.upper()
    _lookup_parents(F, p, tables or {}, links or [], models or {})
    _derive(F)
    F.status_flags = [(c, v, fc) for c, v, fc in getattr(p, "_rate_cols", []) if fc in src.columns]
    for c, v, fc in F.status_flags:
        out[fc] = src[fc].values
    if "_cur" in out.columns:
        money = next((m for m in ("revenue", "gross_revenue", "cost", "profit") if m in out.columns), None)
        if money:
            share = out.loc[out["_ok"].astype(bool)].groupby("_cur")[money].sum().sort_values(ascending=False)
            F.currencies = [str(x) for x in share.index if pd.notna(x)]
            F.currency = F.currencies[0] if F.currencies else None
    return F


def _lookup_parents(F: Frame, p, tables: dict, links: list, models: dict) -> None:
    """Bring numeric attributes (unit cost, unit price, stock...) and concepts from master lists through used links."""
    for l in links:
        if not getattr(l, "use", False) or l.child != p.name or l.parent not in tables:
            continue
        P, pm = tables[l.parent], models.get(l.parent, {})
        if pm.get("file", {}).get("role") != "master":
            continue
        pcols = pm.get("columns", {})
        key = P.df[l.parent_col].astype("string").str.strip()
        child_key = p.df[l.child_col].astype("string").str.strip() if l.child_col in p.df.columns else None
        if child_key is None:
            continue
        for canon in ("unit_cost", "unit_price", "stock_level", "reorder_level"):
            c = _primary(pcols, canon)
            if c and canon not in F.df.columns:
                m = pd.Series(pd.to_numeric(P.df[c], errors="coerce").values, index=key.values)
                m = m[~m.index.duplicated()]
                F.df[canon] = child_key.map(m).values
                F.canon[canon] = f"{l.parent}.{c}"
                F.notes.append(f"{CONCEPTS[canon].label} looked up from {l.parent} through {l.child_col}.")
        for c, v in pcols.items():
            con = CONCEPTS[v["concept"]]
            if con.kind == "group" and c in F.df.columns and c not in sum(F.groups.values(), []):
                F.groups.setdefault(v["concept"], []).append(c)
            elif con.kind == "group" and c not in F.df.columns and v["concept"] not in ("currency",) and c in P.df.columns:
                m = pd.Series(P.df[c].astype("string").str.strip().values, index=key.values)
                m = m[~m.index.duplicated()]
                F.df[c] = child_key.map(m).values
                F.groups.setdefault(v["concept"], []).append(c)


def _derive(F: Frame) -> None:
    d = F.df
    if "revenue" not in d and "gross_revenue" in d:
        net = d["gross_revenue"] - d.get("discount", 0)
        d["revenue"] = net
        F.canon["revenue"] = "gross sales minus discount" if "discount" in d else F.canon["gross_revenue"]
    if "revenue" not in d and {"quantity", "unit_price"} <= set(d.columns):
        d["revenue"] = d["quantity"] * d["unit_price"]
        F.canon["revenue"] = "units x unit price"
        F.notes.append("Revenue is calculated as units x unit price (there is no amount column).")
    if "cost" not in d and {"quantity", "unit_cost"} <= set(d.columns) and F.role not in ("master", "snapshot"):
        d["cost"] = d["quantity"] * d["unit_cost"]
        F.canon["cost"] = "units x unit cost"
        F.notes.append("Cost is calculated as units x unit cost.")
    if "profit" not in d and {"revenue", "cost"} <= set(d.columns):
        d["profit"] = d["revenue"] - d["cost"]
        F.canon["profit"] = "revenue minus cost"
    if {"duration", "promised_duration"} <= set(d.columns):
        d["_late"] = d["duration"] - d["promised_duration"]
        d["_on_time"] = (d["duration"] <= d["promised_duration"]).where(d["duration"].notna() & d["promised_duration"].notna())
    if "stock_level" in d and "unit_cost" in d:
        d["_stock_value"] = d["stock_level"] * d["unit_cost"]
    elif "stock_level" in d and "unit_price" in d:
        d["_stock_value_retail"] = d["stock_level"] * d["unit_price"]

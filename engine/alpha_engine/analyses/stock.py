"""Stock health from a stock file joined to sales: out of stock while selling, running out soon, dead stock, overstock."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, fmt_value

WINDOW = 90


def run(K, sales_frames: list, currency: str | None) -> list[dict]:
    if K is None or "stock_level" not in K.df.columns or "product_id" not in K.df.columns:
        return []
    k = K.df.dropna(subset=["product_id"])
    if K.has_time:
        k = k.sort_values("_t")
    keys = [x for x in (K.item_keys or ["product_id"]) if x in k.columns] or ["product_id"]
    last_rows = k.groupby(keys).tail(1)
    if len(keys) > 1:                               # the same product counted in several stores: add the stores up
        agg = {c: ("sum" if c in ("stock_level", "reorder_level") else ("min" if c == "_expiry" else "first")) for c in last_rows.columns if c not in keys}
        last = last_rows.groupby("product_id").agg(agg)
    else:
        last = last_rows.set_index("product_id")
    ends = [F.df["_t"].max() for F in sales_frames if F is not None and F.has_time] + ([k["_t"].max()] if K.has_time else [])
    asof = max(ends) if ends else pd.Timestamp.now().normalize()          # the last date anywhere in the data
    stock_ids = set(k["product_id"].astype(str).unique())
    def overlaps(F):
        ids = set(F.df["product_id"].dropna().astype(str).unique())
        return len(ids & stock_ids) >= 0.3 * min(len(ids), len(stock_ids)) if ids and stock_ids else False
    S = next((F for F in sales_frames if F is not None and F.has_time and "product_id" in F.df.columns and ("quantity" in F.df.columns or "revenue" in F.df.columns) and overlaps(F)), None)
    out = []
    cost = last["unit_cost"] if "unit_cost" in last.columns else None
    if S is None:                                   # no sales for these items in the files: report what the stock file alone shows
        label = (K.groups.get("name_label") or [None])[0]
        z = last[last.stock_level <= 0]
        if len(z):
            out.append(insight("out_of_stock", "stock", f"{len(z):,} items are out of stock", "Their latest stock count is zero. (No sales file for these items was uploaded, so Alpha cannot tell how fast they sell.)",
                               polarity="bad", actionable=True, numbers={"items": int(len(z))}, source=K.name, tags=["stock"],
                               chart={"type": "table", "title": "Out of stock", "columns": ["Stock"], "fmts": {}, "rows": [{"key": str(i), "name": (str(r[label]) if label and label in r else None), "Stock": float(r.stock_level)} for i, r in z.head(25).iterrows()]},
                               suggestion="Check whether these should be re-ordered."))
        if "reorder_level" in last.columns:
            lowr = last[(last.stock_level > 0) & (last.stock_level <= last.reorder_level)]
            if len(lowr):
                out.append(insight("low_cover", "stock", f"{len(lowr):,} items are at or below their reorder point", "Their latest count is at or below the reorder level in the file.",
                                   polarity="bad", actionable=True, numbers={"items": int(len(lowr))}, source=K.name, tags=["stock"], suggestion="Place re-orders for these items."))
        out += _expiry(K, last, asof, None, currency)
        neg = last[last.stock_level < 0]
        if len(neg):
            out.append(insight("extreme_values", "data", f"{len(neg):,} items show a negative stock count", "A count below zero is usually a counting or entry mistake.", polarity="neutral", actionable=True,
                               numbers={"count": int(len(neg))}, source=K.name, tags=["stock", "data"]))
        return out
    sd = S.df[S.df["_ok"].astype(bool) & S.df["_t"].notna() & S.df["product_id"].notna()]
    end = sd["_t"].max()
    recent = sd[sd["_t"] > end - pd.Timedelta(days=WINDOW)]
    qty_col = "quantity" if "quantity" in sd.columns else None
    daily = (recent.groupby("product_id")[qty_col].sum() if qty_col else recent.groupby("product_id").size()) / WINDOW
    price = (recent.groupby("product_id")["revenue"].sum() / recent.groupby("product_id")[qty_col].sum()) if (qty_col and "revenue" in recent.columns) else None
    ever = set(sd["product_id"].unique())
    t = last.join(daily.rename("daily"), how="left")
    t["daily"] = t["daily"].fillna(0)
    t["cover"] = np.where(t.daily > 0, t.stock_level / t.daily, np.inf)
    label = (K.groups.get("name_label") or [None])[0]
    nm = lambda pid: (str(t.loc[pid, label]) if label and label in t.columns and pd.notna(t.loc[pid, label]) else str(pid))
    unit = qty_col and "units" or "sales"
    # 1. out of stock but selling
    oos = t[(t.stock_level <= 0) & (t.daily > 0)]
    if len(oos):
        lost = float((oos.daily * (price.reindex(oos.index).fillna(0) if price is not None else 0)).sum() * 7) if price is not None else None
        out.append(insight("stockout", "stock", f"{len(oos):,} selling products are out of stock",
                           f"Each sold recently but its latest count is zero." + (f" At recent rates that is about {fmt_value(lost, 'money', currency or '')} of sales a week." if lost else ""),
                           polarity="bad", impact=lost, impact_unit=currency or "", actionable=True, numbers={"items": int(len(oos))},
                           chart=_table("Out of stock, still selling", oos, nm, currency), source=K.name, tags=["stock", "stockout"],
                           suggestion="Re-order these first; they are losing sales every day they are out."))
    # 2. running out within 14 days
    soon = t[(t.stock_level > 0) & (t.cover < 14)]
    if len(soon):
        out.append(insight("low_cover", "stock", f"{len(soon):,} products will run out within 2 weeks at current sales",
                           "Days of cover = stock on hand / average daily sales over the last 90 days.", polarity="bad", actionable=True,
                           numbers={"items": int(len(soon))}, chart=_table("Running out soon", soon.sort_values("cover"), nm, currency), source=K.name, tags=["stock", "cover"],
                           suggestion="Check re-order quantities and lead times for these items."))
    # 3. dead stock
    dead = t[(t.stock_level > 0) & (t.daily == 0)]
    if len(dead):
        val = float((dead.stock_level * cost.reindex(dead.index)).sum()) if cost is not None else None
        never = int(sum(1 for p in dead.index if p not in ever))
        out.append(insight("dead_stock", "stock", f"{len(dead):,} products have stock but no sales in {WINDOW} days",
                           (f"They hold {fmt_value(val, 'money', currency or '')} at cost. " if val else "") + (f"{never:,} of them never sold at all in the data." if never else ""),
                           polarity="bad", impact=val, impact_unit=currency or "", actionable=True, numbers={"items": int(len(dead)), "never_sold": never},
                           chart=_table("No sales in 90 days", dead, nm, currency), source=K.name, tags=["stock", "dead"],
                           suggestion="Consider a clearance price, bundling, or stopping re-orders for these items."))
    out += _expiry(K, last, asof, t, currency)
    # 4. overstock: more than a year of cover on sellers
    over = t[(t.daily > 0) & (t.cover > 365)]
    if len(over) and cost is not None:
        val = float((over.stock_level * cost.reindex(over.index)).sum())
        out.append(insight("overstock", "stock", f"{len(over):,} products hold more than a year of stock",
                           f"Worth {fmt_value(val, 'money', currency or '')} at cost at current sales rates.", polarity="bad", impact=val, impact_unit=currency or "",
                           actionable=True, numbers={"items": int(len(over))}, chart=_table("Over a year of cover", over.sort_values("cover", ascending=False), nm, currency),
                           source=K.name, tags=["stock", "overstock"]))
    return out


def _expiry(K, last, asof, t, currency, window: int = 30) -> list[dict]:
    """Stock that expires soon (or already has), and how much of it will not sell before then at the current pace."""
    if "_expiry" not in last.columns or asof is None:
        return []
    e = pd.to_datetime(last["_expiry"], errors="coerce")
    days = (e - asof).dt.days
    have = last.stock_level.fillna(0) > 0
    soon = have & days.notna() & (days <= window)
    if not soon.any():
        return []
    s = last[soon].assign(days_left=days[soon])
    daily = t["daily"].reindex(s.index).fillna(0) if t is not None else pd.Series(0.0, index=s.index)
    s["unsold"] = (s.stock_level - daily * s.days_left.clip(lower=0)).clip(lower=0)
    cost = s["unit_cost"] if "unit_cost" in s.columns else None
    val = float((s.unsold * cost).sum()) if cost is not None else None
    expired = int((s.days_left < 0).sum())
    label = (K.groups.get("name_label") or [None])[0]
    rows = [{"key": str(i), "name": (str(r[label]) if label and label in r and pd.notna(r[label]) else None), "Stock": float(r.stock_level),
             "Days to expiry": int(r.days_left), "Likely unsold": float(round(r.unsold, 1))} for i, r in s.sort_values("days_left").head(25).iterrows()]
    title = f"{int(soon.sum()):,} products have stock expiring within {window} days" + (f" ({expired} already expired)" if expired else "")
    detail = (f"Counted against {asof:%d %b %Y}, the last date in your data. At the current selling pace about {s.unsold.sum():,.0f} units will not sell before they expire"
              + (f", worth {fmt_value(val, 'money', currency or '')} at cost." if val else "."))
    return [insight("expiry", "stock", title, detail, polarity="bad", impact=val, impact_unit=currency or "", actionable=True,
                    numbers={"items": int(soon.sum()), "expired": expired, "units_at_risk": float(s.unsold.sum())},
                    chart={"type": "table", "title": "Expiring soon", "columns": ["Stock", "Days to expiry", "Likely unsold"], "fmts": {}, "rows": rows},
                    source=K.name, tags=["stock", "expiry"], suggestion="Sell these first (front of shelf, discount, bundle) or return them to the supplier if the terms allow.")]


def _table(title, t, nm, currency):
    rows = []
    for pid, r in t.head(25).iterrows():
        rows.append({"key": str(pid), "name": nm(pid), "Stock": float(r.stock_level), "Sold per day": float(r.daily),
                     "Days of cover": None if not np.isfinite(r.cover) else float(r.cover)})
    return {"type": "table", "title": title, "columns": ["Stock", "Sold per day", "Days of cover"], "fmts": {}, "rows": rows}

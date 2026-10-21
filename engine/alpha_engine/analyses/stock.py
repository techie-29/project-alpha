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
    last = k.groupby("product_id").tail(1).set_index("product_id")
    asof = k["_t"].max() if K.has_time else None
    S = next((F for F in sales_frames if F is not None and F.has_time and "product_id" in F.df.columns and ("quantity" in F.df.columns or "revenue" in F.df.columns)), None)
    out = []
    cost = last["unit_cost"] if "unit_cost" in last.columns else None
    if S is None:
        z = last[last.stock_level <= 0]
        if len(z):
            out.append(insight("out_of_stock", "stock", f"{len(z):,} items are out of stock", "Their latest stock count is zero.", polarity="bad", actionable=True,
                               numbers={"items": int(len(z))}, source=K.name, tags=["stock"]))
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
    # 4. overstock: more than a year of cover on sellers
    over = t[(t.daily > 0) & (t.cover > 365)]
    if len(over) and cost is not None:
        val = float((over.stock_level * cost.reindex(over.index)).sum())
        out.append(insight("overstock", "stock", f"{len(over):,} products hold more than a year of stock",
                           f"Worth {fmt_value(val, 'money', currency or '')} at cost at current sales rates.", polarity="bad", impact=val, impact_unit=currency or "",
                           actionable=True, numbers={"items": int(len(over))}, chart=_table("Over a year of cover", over.sort_values("cover", ascending=False), nm, currency),
                           source=K.name, tags=["stock", "overstock"]))
    return out


def _table(title, t, nm, currency):
    rows = []
    for pid, r in t.head(25).iterrows():
        rows.append({"key": str(pid), "name": nm(pid), "Stock": float(r.stock_level), "Sold per day": float(r.daily),
                     "Days of cover": None if not np.isfinite(r.cover) else float(r.cover)})
    return {"type": "table", "title": title, "columns": ["Stock", "Sold per day", "Days of cover"], "fmts": {}, "rows": rows}

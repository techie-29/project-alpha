"""Unusual values: products sold at a loss, single records far outside the normal range, obvious data problems."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, fmt_value, rows_sample


def run(frames: list, currency: str | None) -> list[dict]:
    out = []
    done_keys = set()
    for F in frames:
        if F is None:
            continue
        d = F.df
        ok = d["_ok"].astype(bool)
        cur = (d["_cur"] == currency) if ("_cur" in d.columns and currency) else pd.Series(True, index=d.index)
        # products (or other entities) sold at a loss
        for key in ("product_id", "site_id", "employee_id"):
            if key in d.columns and {"profit", "revenue"} <= set(d.columns) and key not in done_keys:
                g = d[ok & cur].groupby(key).agg(revenue=("revenue", "sum"), profit=("profit", "sum"), rows=("revenue", "size"))
                g = g[g.rows >= 5]
                if len(g) < 5:
                    continue
                done_keys.add(key)
                loss = g[g.profit < 0].sort_values("profit")
                if len(loss):
                    label = (F.groups.get("name_label") or [None])[0]
                    names = d.groupby(key)[label].first() if label else None
                    word = {"product_id": "products", "site_id": "sites", "employee_id": "staff"}[key]
                    tot = float(loss.profit.sum())
                    out.append(insight("loss_makers", "sales", f"{len(loss):,} {word} sell at a loss",
                                       f"Together they lost {fmt_value(-tot, 'money', currency or '')} on {fmt_value(float(loss.revenue.sum()), 'money', currency or '')} of sales.",
                                       polarity="bad", impact=-tot, impact_unit=currency or "", actionable=True, numbers={"count": int(len(loss))},
                                       chart={"type": "table", "title": f"{word.capitalize()} with negative profit", "columns": ["Revenue", "Profit", "Margin"], "fmts": {"Revenue": "money", "Profit": "money", "Margin": "pct"}, "unit": currency or "",
                                              "rows": [{"key": str(k), "name": (str(names.get(k)) if names is not None else None), "Revenue": float(r.revenue), "Profit": float(r.profit), "Margin": float(r.profit / r.revenue) if r.revenue else None} for k, r in loss.head(20).iterrows()]},
                                       source=F.name, tags=[key, "loss"], suggestion="Check the price, cost and discounts on these; raise prices or stop selling the worst."))
        # single records far outside normal
        for col in [c for c in ("revenue", "quantity", "unit_price", "duration") if c in d.columns]:
            v = d.loc[ok & cur, col].dropna()
            if len(v) < 200 or v.median() <= 0:
                continue
            med, q99 = v.median(), v.quantile(0.99)
            thr = max(20 * med, 3 * q99)
            big = v[v > thr]
            if 0 < len(big) <= max(3, 0.001 * len(v)):
                mask = pd.Series(False, index=d.index); mask.loc[big.index] = True
                out.append(insight("extreme_values", "data", f"{len(big):,} record(s) have an unusually large {col.replace('_', ' ')}",
                                   f"Over {fmt_value(thr, 'money' if col in ('revenue', 'unit_price') else 'number', currency or '')} against a typical {fmt_value(med, 'money' if col in ('revenue', 'unit_price') else 'number', currency or '')}. Worth checking they are not typing or unit mistakes.",
                                   polarity="neutral", actionable=True, numbers={"count": int(len(big)), "threshold": float(thr), "median": float(med)},
                                   evidence=rows_sample(F, mask, [col] + [c for c in ("order_id", "customer_id", "product_id") if c in d.columns], sort_col=col),
                                   source=F.name, tags=[col, "data"]))
        # duplicated ids where each row should be unique
        if F.role == "transactions" and "order_id" in d.columns:
            dup = d["order_id"].duplicated(keep=False) & d["order_id"].notna()
            share = float(dup.mean())
            if 0.001 <= share <= 0.2 and d["order_id"].nunique() > 0.8 * len(d):
                out.append(insight("duplicates", "data", f"{int(dup.sum()):,} rows share an order id with another row",
                                   "In a file with one row per order this usually means duplicated rows. Totals may be overstated by those rows.",
                                   polarity="bad", actionable=True, numbers={"rows": int(dup.sum())}, evidence=rows_sample(F, dup, ["order_id"] + [c for c in ("revenue", "customer_id") if c in d.columns]),
                                   source=F.name, tags=["data", "duplicates"]))
    return out

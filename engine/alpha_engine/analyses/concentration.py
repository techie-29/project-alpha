"""Concentration: how much of the business comes from the top few customers, products, sites..."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, fmt_value

ENTITY_WORD = {"customer_id": "customers", "product_id": "products", "site_id": "sites", "employee_id": "staff", "supplier_id": "suppliers"}


def run(frames: list, currency: str | None) -> list[dict]:
    out, seen = [], set()
    for F in frames:
        if F is None or "revenue" not in F.df.columns:
            continue
        d = F.df[F.df["_ok"].astype(bool)]
        if "_cur" in d.columns and currency:
            d = d[d["_cur"] == currency]
        keys = [k for k in ENTITY_WORD if k in d.columns] + [c for g in ("site_id", "employee_id", "supplier_id") for c in F.groups.get(g, []) if c != F.canon.get(g)]
        for k in dict.fromkeys(keys):
            if k in seen:
                continue
            s = d.groupby(k)["revenue"].sum().sort_values(ascending=False)
            s = s[s > 0]
            n = len(s)
            if n < 5:
                continue
            seen.add(k)
            word = ENTITY_WORD.get(k, k.replace("_", " ") + "s")
            tot = s.sum()
            cum = s.cumsum() / tot
            top1 = s.iloc[0] / tot
            k20 = max(1, int(np.ceil(0.2 * n)))
            top20 = float(cum.iloc[k20 - 1])
            n80 = int((cum < 0.8).sum() + 1)
            pts = [{"x": (i + 1) / n, "y": float(cum.iloc[i])} for i in np.unique(np.linspace(0, n - 1, min(n, 40)).astype(int))]
            chart = {"type": "pareto", "title": f"Share of revenue from the top {word}", "points": pts, "fmt": "pct"}
            if n >= 20 and top20 >= 0.5:
                out.append(insight("concentration", "customers" if k == "customer_id" else "sales",
                                   f"The top 20% of {word} ({k20:,}) bring {top20:.0%} of revenue",
                                   f"{n80:,} of {n:,} {word} make up 80% of revenue. The biggest single one is {top1:.1%}.",
                                   polarity="neutral", impact=float(s.iloc[:k20].sum()), impact_unit=currency or "", impact_share=top20, actionable=k == "customer_id",
                                   numbers={"entities": n, "top20_share": top20, "n80": n80, "top1_share": float(top1)}, chart=chart, source=F.name,
                                   look_at={"col": k, "value": None}, tags=[k, "concentration"], metric="revenue"))
            if top1 >= max(0.2, 2.5 / n) and n >= 5:
                name = str(s.index[0])
                out.append(insight("dependency", "sales", f"One of your {word} ({name}) brings {top1:.0%} of revenue",
                                   f"{name} accounts for {fmt_value(float(s.iloc[0]), 'money', currency or '')} of {fmt_value(float(tot), 'money', currency or '')}. Losing it would hurt; it is worth knowing why it buys so much.",
                                   polarity="bad", impact=float(s.iloc[0]), impact_unit=currency or "", impact_share=float(top1), actionable=True,
                                   numbers={"share": float(top1)}, chart=chart, source=F.name, look_at={"col": k, "value": name}, tags=[k, name], metric="revenue"))
    return out

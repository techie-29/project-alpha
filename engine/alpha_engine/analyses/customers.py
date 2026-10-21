"""Customer behaviour: repeat buying, regular customers who have gone quiet, new-customer flow."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, fmt_value


def run(F, currency: str | None) -> list[dict]:
    if F is None or not F.has_time or "customer_id" not in F.df.columns:
        return []
    d = F.df[F.df["_ok"].astype(bool) & F.df["_t"].notna() & F.df["customer_id"].notna()]
    if "_cur" in d.columns and currency:
        d = d[d["_cur"] == currency]
    if len(d) < 200:
        return []
    out = []
    end = d["_t"].max()
    okey = "order_id" if "order_id" in d.columns else None
    per = d.groupby("customer_id").agg(first=("_t", "min"), last=("_t", "max"), orders=(okey or "_t", "nunique" if okey else "size"),
                                       revenue=("revenue", "sum") if "revenue" in d.columns else ("_t", "size"))
    n = len(per)
    rep = float((per.orders >= 2).mean())
    rev_rep = float(per.loc[per.orders >= 2, "revenue"].sum() / per.revenue.sum()) if "revenue" in d.columns and per.revenue.sum() else None
    out.append(insight("repeat", "customers", f"{rep:.0%} of customers bought more than once",
                       f"{int((per.orders >= 2).sum()):,} of {n:,} customers came back" + (f"; repeat customers bring {rev_rep:.0%} of revenue." if rev_rep is not None else "."),
                       polarity="neutral", numbers={"repeat_rate": rep, "customers": n, "repeat_revenue_share": rev_rep}, source=F.name, tags=["customers", "repeat"]))
    # regulars gone quiet: >= 3 orders, silence longer than twice their usual gap (and 45+ days)
    dd = d.sort_values("_t")
    gaps = dd.groupby("customer_id")["_t"].apply(lambda s: s.drop_duplicates().diff().dt.days.median())
    reg = per[per.orders >= 3].join(gaps.rename("gap"))
    reg["silent"] = (end - reg["last"]).dt.days
    quiet = reg[(reg.silent > np.maximum(2 * reg.gap, 45)) & (reg.gap > 0)]
    if len(quiet) >= 5 and len(reg) >= 20:
        yr = d[d["_t"] >= end - pd.Timedelta(days=365)]
        at_risk = float(yr[yr.customer_id.isin(quiet.index)]["revenue"].sum()) if "revenue" in d.columns else None
        lost_share = len(quiet) / len(reg)
        top = quiet.sort_values("revenue", ascending=False).head(25)
        out.append(insight("quiet_customers", "customers", f"{len(quiet):,} regular customers have gone quiet ({lost_share:.0%} of regulars)",
                           f"They ordered 3 or more times but have not ordered for more than twice their usual gap (and at least 45 days)."
                           + (f" In the last 12 months they spent {fmt_value(at_risk, 'money', currency or '')}." if at_risk else ""),
                           polarity="bad", impact=at_risk, impact_unit=currency or "", actionable=True, look_at={"col": "customer_id", "value": None},
                           numbers={"quiet": int(len(quiet)), "regulars": int(len(reg))},
                           chart={"type": "table", "title": "Quiet regular customers (largest spenders first)", "columns": ["Orders", "Usual gap (days)", "Days since last order", "Total spend"],
                                  "fmts": {"Total spend": "money"}, "unit": currency or "",
                                  "rows": [{"key": str(k), "Orders": int(r.orders), "Usual gap (days)": float(r.gap), "Days since last order": int(r.silent), "Total spend": float(r.revenue)} for k, r in top.iterrows()]},
                           source=F.name, tags=["customers", "churn"], suggestion="Reach out to these customers (a reminder, an offer, or simply asking why they stopped)."))
    # new customers: last 6 complete months vs the same months a year earlier
    first_m = per["first"].dt.to_period("M").value_counts().sort_index()
    months = pd.period_range(d["_t"].min().to_period("M"), end.to_period("M"))
    first_m = first_m.reindex(months, fill_value=0)
    if len(first_m) >= 20:
        cur, prev = first_m.iloc[-7:-1].sum(), first_m.iloc[-19:-13].sum()
        if prev >= 30 and abs(cur - prev) / prev >= 0.15:
            up = cur > prev
            out.append(insight("new_customers", "customers", f"New customers are {'up' if up else 'down'} {abs(cur - prev) / prev:.0%} on a year ago",
                               f"{int(cur):,} new customers in the last 6 complete months against {int(prev):,} in the same months a year earlier.",
                               polarity="good" if up else "bad", actionable=not up, numbers={"recent": int(cur), "year_ago": int(prev)},
                               chart={"type": "line", "title": "New customers per month", "fmt": "count", "x": [p.start_time.strftime("%b %Y") for p in first_m.index], "values": [float(v) for v in first_m.values]},
                               source=F.name, tags=["customers", "acquisition"]))
    return out

"""Impossible values: rows whose numbers cannot all be true at once (profit larger than the sale, a negative price,
a discount above 100%, a finish date before the start date, a sale far from quantity x price).

These rows are NOT removed: the owner decides. Each problem is reported with its rows and with what the totals would be
without them, so the owner (or an examiner) can see how much the headline numbers depend on them. Findings elsewhere in
the report that lean on these rows are marked (see `caution`)."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, fmt_value, rows_sample

FLAG = "_impossible"            # per-row column added to the frame: which check(s) the row failed, or ""


def _fmt(v, cur):
    return fmt_value(float(v), "money", cur or "")


def run(F, currency: str | None) -> list[dict]:
    if F is None:
        return []
    d = F.df
    ok = d["_ok"].astype(bool) if "_ok" in d.columns else pd.Series(True, index=d.index)
    if "_cur" in d.columns and currency:
        ok &= d["_cur"] == currency
    flags = pd.Series("", index=d.index, dtype=object)
    out = []
    keys = [c for c in ("order_id", "customer_id", "product_id") if c in d.columns]

    def add(mask: pd.Series, code: str):
        m = mask & ok
        cur = flags.loc[m]
        flags.loc[m] = np.where(cur == "", code, cur + "," + code)

    # 1. profit larger than the sale itself
    if {"profit", "revenue"} <= set(d.columns):
        rev, pr = d["revenue"], d["profit"]
        bad = ok & rev.gt(0) & pr.gt(rev)
        n = int(bad.sum())
        if n:
            add(bad, "profit_above_sale")
            tot_p, tot_r = float(pr[ok].sum()), float(rev[ok].sum())
            bad_p, bad_r = float(pr[bad].sum()), float(rev[bad].sum())
            clean_p, clean_r = tot_p - bad_p, tot_r - bad_r
            share = bad_p / tot_p if tot_p > 0 else None
            m_all = tot_p / tot_r if tot_r else None
            m_clean = clean_p / clean_r if clean_r else None
            ratio = float((pr[bad] / rev[bad]).median())
            detail = (f"A sale cannot earn more profit than its own value, so these rows are very likely data errors. "
                      f"They carry {_fmt(bad_p, currency)} of profit on only {_fmt(bad_r, currency)} of sales "
                      f"(typically {ratio:.1f}x the sale)."
                      + (f" That is {share:.0%} of all profit in the file." if share is not None and share > 0 else "")
                      + (f" Without them, profit would be {_fmt(clean_p, currency)} and the margin {m_clean:.1%} instead of {m_all:.1%}."
                         if m_all is not None and m_clean is not None else "")
                      + " They are still included in every total until you decide.")
            out.append(insight("data_problem", "data", f"{n:,} rows show more profit than the sale itself",
                               detail, polarity="bad", actionable=True,
                               impact=bad_p, impact_unit=currency or "", impact_share=min(1.0, abs(share)) if share else None,
                               numbers={"rows": n, "rows_share": n / max(int(ok.sum()), 1), "profit_on_rows": bad_p, "sales_on_rows": bad_r,
                                        "profit_all": tot_p, "profit_without": clean_p, "margin_all": m_all, "margin_without": m_clean,
                                        "profit_share": share, "check": "profit_above_sale"},
                               evidence=rows_sample(F, bad, ["revenue", "profit"] + keys, sort_col="profit"),
                               source=F.name, tags=["data", "validation", "profit"], metric="profit",
                               suggestion="Check these rows in the system the file came from (a misplaced decimal or a cost entered as profit is typical) before relying on any profit or margin figure."))

    # 2. negative prices / costs, and discounts that cannot be right
    for col, word in (("unit_price", "unit price"), ("unit_cost", "unit cost")):
        if col in d.columns:
            bad = ok & d[col].lt(0)
            if int(bad.sum()):
                add(bad, f"negative_{col}")
                out.append(insight("data_problem", "data", f"{int(bad.sum()):,} rows have a negative {word}",
                                   f"A {word} below zero is not possible; these rows are probably entry mistakes. They are still included in the totals.",
                                   polarity="bad", actionable=True, numbers={"rows": int(bad.sum()), "check": f"negative_{col}"},
                                   evidence=rows_sample(F, bad, [col] + keys), source=F.name, tags=["data", "validation", col],
                                   suggestion="Correct these rows at the source."))
    if "discount_pct" in d.columns:
        bad = ok & (d["discount_pct"].gt(1) | d["discount_pct"].lt(0))
        if int(bad.sum()):
            add(bad, "discount_out_of_range")
            out.append(insight("data_problem", "data", f"{int(bad.sum()):,} rows have a discount below 0% or above 100%",
                               "A discount outside 0-100% is not possible; these rows are probably entry mistakes. They are still included in the totals.",
                               polarity="bad", actionable=True, numbers={"rows": int(bad.sum()), "check": "discount_out_of_range"},
                               evidence=rows_sample(F, bad, ["discount_pct"] + keys), source=F.name, tags=["data", "validation", "discount"],
                               suggestion="Correct these rows at the source."))

    # 3. a second date before the main date (shipped before ordered, paid before invoiced)
    for col in [c for c in d.columns if str(c).startswith("days_between_")]:
        bad = ok & d[col].lt(0)
        n = int(bad.sum())
        if n:
            add(bad, "date_order")
            what = col[len("days_between_"):].replace("_and_", " before ").replace("_", " ")
            out.append(insight("data_problem", "data", f"{n:,} rows have dates in an impossible order ({what})",
                               "The later step is dated before the earlier one. Time gaps and anything measured from these dates are unreliable for these rows.",
                               polarity="bad", actionable=True, numbers={"rows": n, "check": "date_order"},
                               evidence=rows_sample(F, bad, [col] + keys), source=F.name, tags=["data", "validation", "dates"],
                               suggestion="Check the dates on these rows at the source."))

    # 4. a sale far from quantity x unit price (after discount) - only when that identity holds for most rows
    if {"revenue", "quantity", "unit_price"} <= set(d.columns):
        disc = d["discount_pct"].clip(0, 1) if "discount_pct" in d.columns else 0.0
        est = d["quantity"] * d["unit_price"] * (1 - disc)
        use = ok & est.gt(0) & d["revenue"].gt(0)
        if int(use.sum()) >= 50:
            r = d.loc[use, "revenue"] / est[use]
            med = float(r.median())
            if 0.8 <= med <= 1.25 and float(((r / med).between(0.8, 1.25)).mean()) >= 0.9:      # the identity really holds here
                off = pd.Series(False, index=d.index)
                off.loc[use] = ~(r / med).between(0.2, 5)
                n = int(off.sum())
                if n:
                    add(off, "sale_vs_qty_price")
                    out.append(insight("data_problem", "data", f"{n:,} rows have a sale value far from quantity x unit price",
                                       f"For most rows the sale is about {med:.2f}x quantity x price (after discount); these are more than 5x away. Usually a typing or unit mistake.",
                                       polarity="bad", actionable=True, numbers={"rows": n, "check": "sale_vs_qty_price", "usual_ratio": med},
                                       evidence=rows_sample(F, off, ["revenue", "quantity", "unit_price"] + keys, sort_col="revenue"),
                                       source=F.name, tags=["data", "validation"], suggestion="Check these rows at the source."))
    F.df[FLAG] = flags
    return out


def caution(items: list[dict], F) -> None:
    """Mark findings about a group whose profit or margin rests mostly on impossible rows (e.g. 'margin 13x higher for X'
    when X's profit comes from rows where profit exceeds the sale)."""
    if F is None or FLAG not in F.df.columns or "profit" not in F.df.columns:
        return
    d = F.df
    bad = d[FLAG].astype(str).str.contains("profit_above_sale")
    if not bad.any():
        return
    for i in items:
        la = i.get("look_at") or {}
        col, val = la.get("col"), la.get("value")
        if i.get("type") == "data_problem" or col not in d.columns or val is None:
            continue
        text = (i.get("title", "") + " " + str(i.get("metric") or "")).lower()
        if not any(w in text for w in ("profit", "margin")):
            continue
        g = d[col].astype(str) == str(val)
        gp = float(d.loc[g & d["profit"].gt(0), "profit"].sum())
        bp = float(d.loc[g & bad, "profit"].sum())
        if gp > 0 and bp / gp >= 0.5:
            i["caution"] = (f"Caution: {bp / gp:.0%} of the profit behind this finding comes from rows where profit is larger than the sale "
                            f"(flagged as likely data errors). It may not be real.")
            i["detail"] = i["detail"] + " " + i["caution"]
            i["polarity"] = "neutral"

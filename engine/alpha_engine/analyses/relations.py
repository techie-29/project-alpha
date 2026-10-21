"""Relationships: measures that move together row by row (late deliveries vs ratings, discounts vs returns, age vs spend)."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, apply_bh, fmt_value, leaks
from scipy.stats import spearmanr, norm

MIN_ROWS = 200


def variables(F) -> list[tuple[str, str, str, int]]:
    """(column, label, fmt, polarity) of per-row behaviour variables (not plain money totals that just scale with size)."""
    d, V = F.df, []
    add = lambda c, lab, fmt, pol: V.append((c, lab, fmt, pol)) if c in d.columns and d[c].notna().sum() >= MIN_ROWS and d[c].nunique() >= 2 else None
    u = F.duration_unit
    if "_late" in d.columns:
        add("_late", f"delay vs promise ({u})", "days", -1)
    else:
        add("duration", f"time taken ({u})", "days", -1)
    if "discount_pct" in d.columns and "_disc_share" not in d.columns:
        add("discount_pct", "discount share", "pct", 0)
    for g in F.gaps:
        add(g, g.replace("days_between_", "days between ").replace("_and_", " and ").replace("_", " "), "number", 0)
    add("age", "customer age", "number", 0)
    add("quantity", "units per order", "number", +1)
    if "revenue" in d.columns and F.role == "transactions":
        add("revenue", "order value", "money", +1)
    if {"discount", "gross_revenue"} <= set(d.columns):
        d["_disc_share"] = (d["discount"] / d["gross_revenue"].where(d["gross_revenue"] > 0)).clip(0, 1)
        add("_disc_share", "discount share", "pct", 0)
    elif "discount_pct" in d.columns:
        add("discount_pct", "discount share", "pct", 0)
    if {"profit", "revenue"} <= set(d.columns):
        d["_margin_row"] = (d["profit"] / d["revenue"].where(d["revenue"] > 0)).clip(-2, 1)
        add("_margin_row", "margin", "pct", +1)
    add("unit_price", "unit price", "money", 0)
    for c, cid in F.extra_numbers[:6]:
        if c in F.attributes:
            continue                                 # a customer's lifetime value is not a property of each order
        if cid in ("points", "activity_count", "percent", "number", "money_other") and c in d.columns:
            add(c, c.replace("_", " "), "number", 0)
    add("rating", "rating", "rating", +1)                # a result: always the second variable
    seen, out = set(), []
    for v in V:
        if v[0] not in seen:
            seen.add(v[0]); out.append(v)
    return out


def outcomes(F) -> list[tuple[str, str, int]]:
    from .targets import targets
    out = [(t.num, t.label[0].lower() + t.label[1:], t.polarity) for t in targets(F) if t.kind == "rate" and t.num.startswith("__rate__")]
    if "_on_time" in F.df.columns:
        out.append(("_on_time", "on-time rate", +1))
    return out


def _drop_size_twins(F, V):
    """Keep one 'size of the order' variable: points, line counts etc. that just follow order value say nothing new."""
    d = F.df
    size = next((c for c in ("revenue", "quantity") if any(v[0] == c for v in V)), None)
    if size is None:
        return V
    keep = []
    for v in V:
        if v[0] not in (size, "rating", "_late", "duration", "age", "_disc_share", "_margin_row", "discount_pct", "unit_price"):
            sub = d.loc[d["_ok"].astype(bool), [size, v[0]]].dropna()
            sub = sub[(sub[size] != 0) & (sub[v[0]] != 0)]
            if len(sub) > 50:
                r, _ = spearmanr(sub[size].to_numpy()[:50000], sub[v[0]].to_numpy()[:50000])
                if abs(r) >= 0.7:
                    continue
        keep.append(v)
    return keep


SAME_FAMILY = [{"_late", "duration"}, {"revenue", "quantity"}, {"_margin_row", "_disc_share"}, {"revenue", "unit_price"}, {"quantity", "unit_price"}]
DERIVED_OUTCOME = {"_on_time": {"_late", "duration"}}
RESULTS = {"rating"}
NOT_BEFORE_OUTCOME = {"_margin_row", "revenue", "rating"}      # computed after the outcome is known (cancelled orders earn nothing)


def run(F, currency: str | None) -> list[dict]:
    if F is None or F.role not in ("transactions", "lines"):
        return []
    d = F.df
    V = _drop_size_twins(F, variables(F))
    out = []
    base = d["_cur"] == currency if ("_cur" in d.columns and currency) else pd.Series(True, index=d.index)
    for i in range(len(V)):
        for j in range(i + 1, len(V)):
            (x, xl, xf, xp), (y, yl, yf, yp) = V[i], V[j]
            if any({x, y} <= s for s in SAME_FAMILY):
                continue
            if {x, y} <= {"revenue", "quantity"}:
                continue
            if "money" in (xf, yf):
                mk = base & d["_ok"].astype(bool)
            else:
                mk = d["_ok"].astype(bool)
            sub = d.loc[mk, [x, y]].dropna()
            if len(sub) < MIN_ROWS:
                continue
            xs, ys = sub[x].to_numpy(float), sub[y].to_numpy(float)
            if len(xs) > 50000:
                ii = np.random.default_rng(1).choice(len(xs), 50000, replace=False); xs, ys = xs[ii], ys[ii]
            r, p = spearmanr(xs, ys)
            r, p = float(r), float(p)
            if not np.isfinite(r):
                continue
            if abs(r) < 0.15:
                continue
            # describe with bins of x
            try:
                bins = pd.qcut(sub[x].rank(method="first"), 5, labels=False)
            except ValueError:
                continue
            g = sub.groupby(bins).agg(xm=(x, "median"), ym=(y, "mean"), n=(y, "size"))
            lo, hi = g.iloc[0], g.iloc[-1]
            head = f"{yl[0].upper() + yl[1:]} is {'higher' if r > 0 else 'lower'} when {xl} is higher"
            det = (f"When {xl} is lowest (around {fmt_value(lo.xm, xf, F.duration_unit if xf == 'days' else currency or '')}), {yl} averages {fmt_value(lo.ym, yf, F.duration_unit if yf == 'days' else currency or '')}; "
                   f"when it is highest (around {fmt_value(hi.xm, xf, F.duration_unit if xf == 'days' else currency or '')}), {fmt_value(hi.ym, yf, F.duration_unit if yf == 'days' else currency or '')}. Rank correlation {r:+.2f}.")
            # the outcome (y) getting worse as x rises is a problem to work on; getting better is worth keeping
            pol = 0 if not yp else (1 if r * yp > 0 else -1)
            out.append(insight("relationship", "service" if "rating" in (x, y) else "operations" if "_late" in (x, y) else "sales", head, det, p=p,
                               polarity="neutral" if pol == 0 else ("good" if pol > 0 else "bad"), actionable=True,
                               numbers={"rho": r, "low_x": float(lo.xm), "low_y": float(lo.ym), "high_x": float(hi.xm), "high_y": float(hi.ym), "rows": int(len(sub))},
                               chart={"type": "binned", "title": f"Average {yl} by {xl} (five equal groups)", "fmt": yf, "x_fmt": xf,
                                      "rows": [{"group": fmt_value(row.xm, xf, currency or ''), "value": float(row.ym), "rows": int(row.n)} for _, row in g.iterrows()], "keep_order": True},
                               source=F.name, tags=[x, y, "relationship"], note="A relationship in the data, not proof that one causes the other."))
    # numeric variable vs outcome rates (e.g. delay vs returns), outcomes measured on all rows
    for (x, xl, xf, xp) in V:
        if x in RESULTS:
            continue
        for (o, ol, op) in outcomes(F):
            if x in DERIVED_OUTCOME.get(o, set()) or (o.startswith("__rate__") and x in NOT_BEFORE_OUTCOME):
                continue
            if leaks(d[o].fillna(False).astype(float).to_numpy(), d[x]):
                continue
            sub = d.loc[d[x].notna() & d[o].notna(), [x, o]]
            if len(sub) < MIN_ROWS or sub[o].astype(float).mean() in (0.0, 1.0):
                continue
            try:
                bins = pd.qcut(sub[x].rank(method="first"), 5, labels=False).to_numpy()
            except ValueError:
                continue
            yv = sub[o].astype(float).to_numpy()
            rates = pd.Series(yv).groupby(bins).mean()
            cnts = pd.Series(yv).groupby(bins).size()
            lo_r, hi_r = rates.iloc[0], rates.iloc[-1]
            if abs(hi_r - lo_r) < 0.02 or max(hi_r, lo_r) / max(min(hi_r, lo_r), 1e-9) < 1.3:
                continue
            pool = (lo_r * cnts.iloc[0] + hi_r * cnts.iloc[-1]) / (cnts.iloc[0] + cnts.iloc[-1])
            se = np.sqrt(pool * (1 - pool) * (1 / cnts.iloc[0] + 1 / cnts.iloc[-1]))
            p = float(2 * norm.sf(abs(hi_r - lo_r) / se)) if se > 0 else 1.0
            xm = sub.groupby(bins)[x].median()
            out.append(insight("relationship", "operations", f"{ol[0].upper() + ol[1:]} {'rises' if hi_r > lo_r else 'falls'} with {xl}",
                               f"{ol[0].upper() + ol[1:]} is {lo_r:.1%} when {xl} is lowest (around {fmt_value(xm.iloc[0], xf, F.duration_unit if xf == 'days' else currency or '')}) and {hi_r:.1%} when it is highest (around {fmt_value(xm.iloc[-1], xf, F.duration_unit if xf == 'days' else currency or '')}).",
                               p=min(p, 1.0), polarity="bad" if (hi_r > lo_r) == (op < 0) else "good", actionable=True,
                               numbers={"low_rate": float(lo_r), "high_rate": float(hi_r), "rows": int(len(sub))},
                               chart={"type": "binned", "title": f"{ol[0].upper() + ol[1:]} by {xl} (five equal groups)", "fmt": "pct", "x_fmt": xf,
                                      "rows": [{"group": fmt_value(xm.iloc[k], xf, currency or ''), "value": float(rates.iloc[k])} for k in range(len(rates))], "keep_order": True},
                               source=F.name, tags=[x, o, "relationship"], note="A relationship in the data, not proof that one causes the other."))
    return apply_bh(out)

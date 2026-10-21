"""Trends, seasonality, weekday rhythm and shifting shares, on complete calendar months."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, apply_bh, fmt_value, RNG_SEED
from ..metrics.catalogue import available, series, BY_ID, _agg

TREND_METRICS = ("revenue", "orders", "transactions", "customers", "aov", "margin", "units", "on_time_rate", "avg_late", "avg_duration", "avg_rating", "discount_rate")


def _complete_months(F, labels, vals):
    t = F.df["_t"].dropna()
    first, last = t.min(), t.max()
    lo = 0 if first.day <= 2 else 1
    hi = len(vals) if last.normalize() >= (last + pd.offsets.MonthEnd(0)).normalize() - pd.Timedelta(days=1) else len(vals) - 1
    return labels[lo:hi], np.array([np.nan if v is None else v for v in vals[lo:hi]], dtype=float)


def _block_perm_rho(y: np.ndarray, B: int = 999, block: int = 3, rng=None) -> tuple[float, float]:
    rng = rng or np.random.default_rng(RNG_SEED)
    ok = np.isfinite(y)
    y = y[ok]
    n = len(y)
    x = np.arange(n)
    rk = lambda a: pd.Series(a).rank().to_numpy()
    ry = rk(y); rx = rk(x)
    r = float(np.corrcoef(rx, ry)[0, 1])
    blocks = [np.arange(i, min(i + block, n)) for i in range(0, n, block)]
    ge = 0
    for _ in range(B):
        order = np.concatenate([blocks[j] for j in rng.permutation(len(blocks))])
        ge += abs(np.corrcoef(rx, ry[order])[0, 1]) >= abs(r) - 1e-12
    return r, (ge + 1) / (B + 1)


def run(F, currency: str | None) -> list[dict]:
    if F is None or not F.has_time:
        return []
    out = []
    ms = {m.id: m for m in available(F)}
    for col, val, fc in F.status_flags:
        if f"rate:{fc}" in ms:
            pass
    ids = [i for i in TREND_METRICS if i in ms] + [i for i in ms if i.startswith("rate:")]
    for mid in ids:
        m = ms[mid]
        labels, vals = series(F, m, "month", currency if m.money else None)
        labels, y = _complete_months(F, labels, vals)
        if np.isfinite(y).sum() < 12:
            continue
        r, p = _block_perm_rho(y)
        n6 = 6 if len(y) >= 18 else 3
        a, b = np.nanmean(y[:n6]), np.nanmean(y[-n6:])
        if m.fmt == "pct":
            material = abs(b - a) >= 0.02
            chg = f"from {a * 100:.1f}% to {b * 100:.1f}%"
        else:
            material = a != 0 and abs(b - a) / abs(a) >= 0.10
            chg = f"from {fmt_value(a, m.fmt, currency or '')} to {fmt_value(b, m.fmt, currency or '')} a month" if m.spec[0] in ("sum", "count", "nunique") else \
                  f"from {fmt_value(a, m.fmt, currency or '')} to {fmt_value(b, m.fmt, currency or '')}"
        if not material:
            continue
        up = b > a
        good = bool((m.polarity > 0) == bool(up)) if m.polarity else None
        rel = (b - a) / abs(a) if a and m.fmt != "pct" else None
        head = f"{m.label} has been {'rising' if up else 'falling'} steadily" + (f" ({rel:+.0%} over the period)" if rel is not None else "")
        out.append(insight("trend", m.area, head, f"Average of the first {n6} months against the last {n6}: {chg}.", p=p,
                           polarity="good" if good else ("bad" if good is False else "neutral"), metric=mid, metric_label=m.label,
                           numbers={"start": a, "end": b, "rho": r, "fmt": m.fmt, "months": int(np.isfinite(y).sum())},
                           chart={"type": "line", "title": f"{m.label} per month", "fmt": m.fmt, "unit": currency if m.money else "", "x": labels, "values": [None if not np.isfinite(v) else float(v) for v in y]},
                           source=F.name, tags=[mid, "trend"]))
    main = ms.get("revenue") or ms.get("orders") or ms.get("transactions")
    if main:
        out += _seasonality(F, main, currency)
        out += _weekday(F, main, currency)
        out += _share_shifts(F, main, currency)
    return apply_bh(out)


def _seasonality(F, m, currency):
    labels, vals = series(F, m, "month", currency if m.money else None)
    labels, y = _complete_months(F, labels, vals)
    idx = pd.to_datetime(pd.Series(labels), format="%b %Y")
    df = pd.DataFrame({"y": y, "year": idx.dt.year.values, "month": idx.dt.month.values}).dropna()
    full_years = df.groupby("year").size()
    years = full_years[full_years >= 10].index
    df = df[df.year.isin(years)]
    if len(years) < 2:
        return []
    df["rel"] = df.y / df.groupby("year").y.transform("mean")
    prof = df.groupby("month").rel.mean()
    if len(prof) < 12:
        return []
    rng = np.random.default_rng(RNG_SEED)
    stat = prof.var()
    ge = 0
    for _ in range(499):
        sh = df.groupby("year").rel.transform(lambda s: rng.permutation(s.values))
        ge += df.assign(r2=sh).groupby("month").r2.mean().var() >= stat
    p = (ge + 1) / 500
    hi, lo = int(prof.idxmax()), int(prof.idxmin())
    if prof.max() - 1 < 0.12:
        return []
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return [insight("seasonality", m.area, f"{m.label} peaks every year in {names[hi - 1]} ({prof.max() - 1:+.0%} on an average month)",
                    f"Across {len(years)} years, {names[hi - 1]} is the strongest month and {names[lo - 1]} the weakest ({prof.min() - 1:+.0%}). Plan stock and staff around it.",
                    p=p, polarity="neutral", metric=m.id, metric_label=m.label, actionable=True,
                    numbers={"peak_month": names[hi - 1], "peak": float(prof.max() - 1), "low_month": names[lo - 1], "low": float(prof.min() - 1), "years": len(years)},
                    chart={"type": "bar", "title": f"{m.label}: each month against an average month", "fmt": "pct", "rows": [{"group": names[i - 1], "value": float(prof[i] - 1)} for i in prof.index], "keep_order": True, "focus": names[hi - 1]},
                    source=F.name, tags=[m.id, "seasonality"])]


def _weekday(F, m, currency):
    d = F.df[F.df["_ok"].astype(bool) & F.df["_t"].notna()]
    if m.money and "_cur" in d.columns and currency:
        d = d[d["_cur"] == currency]
    if m.spec[0] not in ("sum", "count", "nunique"):
        return []
    day = d["_t"].dt.normalize()
    if day.nunique() < 56 or (d["_t"].dt.hour.nunique() > 1 and False):
        return []
    if m.spec[0] == "sum":
        daily = d.groupby(day)[m.spec[1]].sum()
    else:
        daily = d.groupby(day).size()
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()), fill_value=0)
    wd = daily.index.weekday
    means = daily.groupby(wd).mean()
    if len(means) < 7:
        return []
    rel = means / means.mean()
    rng = np.random.default_rng(RNG_SEED)
    stat = rel.var()
    v = daily.to_numpy()
    ge = sum(pd.Series(rng.permutation(v)).groupby(wd).mean().pipe(lambda s: (s / s.mean()).var()) >= stat for _ in range(499))
    p = (ge + 1) / 500
    if rel.max() - 1 < 0.12:
        return []
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hi, lo = int(rel.idxmax()), int(rel.idxmin())
    return [insight("weekday", m.area, f"{names[hi]} is the busiest day ({rel.max() - 1:+.0%} on an average day); {names[lo]} the quietest ({rel.min() - 1:+.0%})",
                    "Measured on daily totals across the whole period. Useful for staffing, promotions and stock top-ups.", p=p, polarity="neutral", actionable=True,
                    metric=m.id, metric_label=m.label, numbers={"busiest": names[hi], "quietest": names[lo]},
                    chart={"type": "bar", "title": f"{m.label} by weekday, against an average day", "fmt": "pct", "rows": [{"group": names[i][:3], "value": float(rel[i] - 1)} for i in range(7)], "keep_order": True, "focus": names[hi][:3]},
                    source=F.name, tags=[m.id, "weekday"])]


def _share_shifts(F, m, currency):
    if m.spec[0] != "sum":
        return []
    out = []
    d = F.df[F.df["_ok"].astype(bool) & F.df["_t"].notna()]
    if m.money and "_cur" in d.columns and currency:
        d = d[d["_cur"] == currency]
    mon = d["_t"].dt.to_period("M")
    months = sorted(mon.unique())
    if len(months) < 12:
        return []
    months = months[1:-1] if len(months) > 14 else months
    for g in ("channel", "location", "product_group", "segment", "payment_method", "delivery_method", "site_id", "campaign"):
        for col in F.groups.get(g, [])[:2]:
            if col not in d.columns or not (2 <= d[col].nunique() <= 10):
                continue
            tab = d.groupby([mon, d[col]])[m.spec[1]].sum().unstack(fill_value=0)
            tab = tab.reindex(months).fillna(0)
            share = tab.div(tab.sum(axis=1).replace(0, np.nan), axis=0)
            n6 = 6 if len(share) >= 18 else 3
            for grp in share.columns:
                y = share[grp].to_numpy(dtype=float)
                a, b = np.nanmean(y[:n6]), np.nanmean(y[-n6:])
                if abs(b - a) < 0.05:
                    continue
                r, p = _block_perm_rho(y, B=499)
                up = b > a
                out.append(insight("share_shift", m.area, f"{grp}'s share of {m.label.lower()} {'rose' if up else 'fell'} from {a:.0%} to {b:.0%} ({col.replace('_', ' ')})",
                                   f"Average share in the first {n6} months against the last {n6}. The mix is moving{' towards' if up else ' away from'} {grp}.", p=p,
                                   polarity="neutral", actionable=True, look_at={"col": col, "value": str(grp)}, metric=m.id, metric_label=m.label,
                                   numbers={"start": a, "end": b},
                                   chart={"type": "stacked", "title": f"Share of {m.label.lower()} by {col.replace('_', ' ')}", "fmt": "pct", "x": [p_.start_time.strftime('%b %Y') for p_ in share.index],
                                          "series": [{"name": str(c), "values": [None if not np.isfinite(v) else float(v) for v in share[c].values]} for c in share.columns], "focus": str(grp)},
                                   source=F.name, tags=[col, str(grp), "mix"]))
    return out

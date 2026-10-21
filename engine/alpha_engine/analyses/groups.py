"""Group differences: which groups (region, channel, warehouse, product category...) are clearly better or worse than the rest."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, perm_group_test, apply_bh, codes_of, fmt_value, rows_sample, MIN_GROUP_ROWS, ratio_z, leaks
from .targets import targets, group_columns


def material(t, a, b) -> bool:
    if not (np.isfinite(a) and np.isfinite(b)):
        return False
    if t.fmt == "pct":
        return abs(a - b) >= 0.02 and (b == 0 or abs(a - b) / max(abs(b), 1e-9) >= 0.2)
    if t.fmt in ("rating",):
        return abs(a - b) >= 0.15
    if t.fmt == "days":
        return abs(a - b) >= 0.5 and abs(a - b) / max(abs(b), 1e-9) >= 0.1
    return abs(a - b) / max(abs(b), 1e-9) >= 0.12


def _group_series(s: pd.Series, leak: bool = False) -> pd.Series:
    """Missing values become their own group ('(none)') when they are a real share of rows, e.g. orders with no campaign."""
    miss = s.isna().mean()
    if 0.05 <= miss <= 0.95:
        return s.astype("string").fillna("(none)")
    return s


def run(F, currency: str | None, avg_order: float | None, skip_cols: set | None = None, max_tests: int = 120) -> list[dict]:
    out = []
    cols = [c for c in group_columns(F) if c not in (skip_cols or set())]
    status_cols = set(F.groups.get("status", []))
    flag_src = {fc: c for c, v, fc in F.status_flags}
    n_tests = 0
    for t in targets(F):
        m, num, den = t.arrays(F, currency)
        if m.sum() < 100:
            continue
        for col in cols:
            if n_tests >= max_tests:
                break
            if t.kind == "rate" and (col == flag_src.get(t.num) or col in status_cols):
                continue                                   # 'cancel rate by status' says nothing new
            if t.kind == "rate" and leaks(num[m], F.df[col][m]):
                continue                                   # the column only exists for some outcomes
            s = _group_series(F.df[col])
            mm = m & s.notna().to_numpy()
            codes, uniq = codes_of(s[mm])
            k = len(uniq)
            cnt = np.bincount(codes, minlength=k)
            big = cnt >= MIN_GROUP_ROWS
            if big.sum() < 2:
                continue
            keep = big[codes]
            cc, nn, dd = codes[keep], num[mm][keep], den[mm][keep]
            n_tests += 1
            gn = np.bincount(cc, weights=nn, minlength=k); gd = np.bincount(cc, weights=dd, minlength=k)
            TN0, TD0 = nn.sum(), dd.sum()
            v0 = gn / np.where(gd > 0, gd, np.nan)
            rest0 = (TN0 - gn) / np.where(TD0 - gd > 0, TD0 - gd, np.nan)
            med0 = np.nanmedian(v0[big]) if big.any() else np.nan
            promising = [j for j in np.nonzero(big)[0] if material(t, v0[j], rest0[j]) and (big.sum() == 2 or material(t, v0[j], med0))]
            if not promising:
                continue
            _, pz = ratio_z(nn, dd, cc, k)
            if min(pz[j] for j in promising) > 0.01:
                continue                                   # nothing close to significant: skip the slow shuffle test
            obs, p = perm_group_test(nn, dd, cc, k, B1=199, B2=999)
            TN, TD = nn.sum(), dd.sum()
            vals = gn / np.where(gd > 0, gd, np.nan)
            bigs = sorted(np.nonzero(big)[0], key=lambda j: cnt[j])          # smaller groups first (for the two-group case)
            allv = [vals[j] for j in bigs if np.isfinite(vals[j])]
            typical_all = float(np.median(allv)) if allv else np.nan
            reported = []
            for g in bigs:
                a = vals[g]
                b = (TN - gn[g]) / (TD - gd[g]) if TD - gd[g] > 0 else np.nan
                typical = typical_all if len(bigs) > 2 else b
                # must stand out against the rest AND against a typical other group (so 'the rest are lower' is not repeated)
                if not material(t, a, b) or not material(t, a, typical) or not np.isfinite(p[g]):
                    continue
                if len(bigs) == 2 and reported:
                    continue                                   # two groups: one finding says it all
                reported.append(g)
                up = a > b
                good = bool((t.polarity > 0) == bool(up)) if t.polarity else None
                gname = str(uniq[g])
                colname = col.replace("_", " ")
                rows_g = int(cnt[g])
                if t.fmt == "pct" and b > 0 and a / b >= 1.5:
                    head = f"{t.label} is {a / b:.1f}x higher for {gname} ({colname})"
                elif t.fmt == "pct" and a > 0 and b / a >= 1.5:
                    head = f"{t.label} is {b / a:.1f}x lower for {gname} ({colname})"
                else:
                    rel = (a - b) / abs(b) if b else 0
                    head = f"{t.label} is {abs(rel):.0%} {'higher' if up else 'lower'} for {gname} ({colname})" if t.fmt not in ("pct", "rating", "days") else \
                           f"{t.label} is {'higher' if up else 'lower'} for {gname} ({colname})"
                detail = f"{fmt_value(a, t.fmt, currency or '')} for {gname} against {fmt_value(b, t.fmt, currency or '')} for everything else ({rows_g:,} rows)."
                impact, unit, what = None, "", None
                if t.kind == "rate":
                    excess = (a - b) * rows_g
                    what = f"about {abs(excess):,.0f} {'more' if excess > 0 else 'fewer'} {'cases' if t.polarity < 0 else 'on-time cases'} than if it matched the rest"
                    if avg_order and t.polarity < 0 and excess > 0:
                        impact, unit = excess * avg_order, currency or ""
                        what += f", roughly {fmt_value(impact, 'money', unit)} of orders"
                elif t.id == "margin":
                    impact, unit = (a - b) * gd[g], currency or ""
                    what = f"profit {fmt_value(abs(impact), 'money', unit)} {'above' if impact > 0 else 'below'} what the usual margin would give on its sales"
                elif t.money:
                    impact, unit = (a - b) * gd[g], currency or ""
                    what = f"{fmt_value(abs(impact), 'money', unit)} {'more' if impact > 0 else 'less'} than if it matched the rest"
                if what:
                    detail += " That is " + what + "."
                rows = [{"group": str(uniq[j]), "value": float(vals[j]), "rows": int(cnt[j])} for j in np.argsort(-vals) if big[j] and np.isfinite(vals[j])][:14]
                ev_mask = pd.Series(False, index=F.df.index)
                ev_mask.loc[F.df.index[mm][codes == g]] = True
                if t.kind == "rate" and t.num in F.df.columns:
                    ev_mask &= F.df[t.num].fillna(False).astype(bool) if t.polarity < 0 else ~F.df[t.num].fillna(True).astype(bool)
                ev = rows_sample(F, ev_mask, [col, t.num] + ([t.den] if t.den else []) + [c for c in ("order_id", "customer_id", "product_id", "revenue") if c in F.df.columns],
                                 sort_col="revenue" if "revenue" in F.df.columns else None)
                out.append(insight("group_difference", _area(t), head, detail, p=float(p[g]), polarity="good" if good else ("bad" if good is False else "neutral"),
                                   impact=impact, impact_unit=unit, actionable=True, look_at={"col": col, "value": gname},
                                   numbers={"group": a, "rest": b, "rows": rows_g, "fmt": t.fmt, "unit": currency if t.money else ""},
                                   chart={"type": "bar", "title": f"{t.label} by {colname}", "fmt": t.fmt, "unit": currency if t.money else "", "rows": rows, "focus": gname},
                                   evidence=ev, source=F.name, metric=t.id, metric_label=t.label, tags=[col, gname]))
    return apply_bh(out)


def _area(t):
    if t.id in ("margin", "discount_rate", "aov", "avg_sale"):
        return "sales"
    if t.id == "rating":
        return "service"
    return "operations"

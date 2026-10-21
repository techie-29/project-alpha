"""Open exploration: no checklist. For each measure, search combinations of two groups for cells that behave
very differently from what each group alone would suggest (e.g. returns are 3x for warehouse X + Economy shipping)."""
from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
from .common import insight, perm_group_test, apply_bh, codes_of, fmt_value, rows_sample
from .targets import targets, group_columns
from .groups import material, _group_series

MIN_CELL = 40


def run(F, currency: str | None, max_cols: int = 8, max_tests: int = 60) -> list[dict]:
    if F is None or F.role not in ("transactions", "lines"):
        return []
    cols = [c for c in group_columns(F, max_levels=25) if c not in F.groups.get("status", [])][:max_cols]
    if len(cols) < 2:
        return []
    out, tests = [], 0
    for t in targets(F):
        m, num, den = t.arrays(F, currency)
        if m.sum() < 300:
            continue
        N, D = num[m], den[m]
        overall = N.sum() / D.sum()
        cand = []
        for c1, c2 in itertools.combinations(cols, 2):
            s1 = _group_series(F.df[c1])[m].astype("string").fillna("?").to_numpy()
            s2 = _group_series(F.df[c2])[m].astype("string").fillna("?").to_numpy()
            key = pd.Series(s1 + "\u0001" + s2)
            g = pd.DataFrame({"k": key, "a": s1, "b": s2, "n": N, "d": D})
            cell = g.groupby("k").agg(n=("n", "sum"), d=("d", "sum"), rows=("n", "size"), a=("a", "first"), b=("b", "first"))
            cell = cell[cell.rows >= MIN_CELL]
            if cell.empty:
                continue
            va = g.groupby("a").agg(n=("n", "sum"), d=("d", "sum")); va = va.n / va.d
            vb = g.groupby("b").agg(n=("n", "sum"), d=("d", "sum")); vb = vb.n / vb.d
            cell["v"] = cell.n / cell.d
            cell["ea"] = cell.a.map(va); cell["eb"] = cell.b.map(vb)
            # what the two groups would predict together if their effects simply combined
            if overall > 0 and (N >= 0).all():
                cell["exp"] = cell.ea * cell.eb / overall                 # effects multiply (rates, averages of positive values)
            else:
                cell["exp"] = cell.ea + cell.eb - overall                 # effects add (margins, values that can be negative)
            cell["gap"] = (cell.v - cell["exp"]).abs()
            for k, r in cell.sort_values("gap", ascending=False).head(2).iterrows():
                beyond = (r.v > max(r.ea, r.eb, r.exp)) if r.v >= overall else (r.v < min(r.ea, r.eb, r.exp))
                if beyond and material(t, r.v, r.exp) and material(t, r.v, overall):
                    cand.append((r.gap * np.sqrt(r.rows), c1, c2, r))
        for score, c1, c2, r in sorted(cand, key=lambda x: -x[0])[:4]:
            if tests >= max_tests:
                break
            tests += 1
            # shuffle test inside each parent group: does the cell differ from the rest of A, and from the rest of B?
            ps = []
            for col_in, val_in, col_other, val_other in ((c1, r.a, c2, r.b), (c2, r.b, c1, r.a)):
                inside = m & (_group_series(F.df[col_in]).astype("string").fillna("?") == val_in).to_numpy()
                cc, uu = codes_of(_group_series(F.df[col_other])[inside].astype("string").fillna("?"))
                j = int(np.where(uu == val_other)[0][0]) if (uu == val_other).any() else None
                if j is None or len(uu) < 2:
                    ps.append(1.0); continue
                _, p = perm_group_test(num[inside], den[inside], cc, len(uu), B1=199, B2=999)
                ps.append(float(p[j]))
            p = max(ps)
            up = r.v > overall
            good = (t.polarity > 0) == up if t.polarity else None
            a_, b_ = str(r.a), str(r.b)
            head = f"{t.label} is {'especially high' if up else 'especially low'} for {a_} + {b_}"
            det = (f"{fmt_value(r.v, t.fmt, currency or '')} for {c1.replace('_', ' ')} {a_} with {c2.replace('_', ' ')} {b_} ({int(r.rows):,} rows), "
                   f"against {fmt_value(r.ea, t.fmt, currency or '')} for all of {a_}, {fmt_value(r.eb, t.fmt, currency or '')} for all of {b_}, and {fmt_value(overall, t.fmt, currency or '')} overall. "
                   f"The two together would suggest about {fmt_value(r.exp, t.fmt, currency or '')}, so this combination stands out on its own.")
            mask = pd.Series(m, index=F.df.index) & (_group_series(F.df[c1]).astype("string") == a_) & (_group_series(F.df[c2]).astype("string") == b_)
            out.append(insight("combination", "operations" if t.kind == "rate" else "sales", head, det, p=p,
                               polarity="good" if good else ("bad" if good is False else "neutral"), actionable=True,
                               look_at={"col": c1, "value": a_, "col2": c2, "value2": b_}, metric=t.id, metric_label=t.label,
                               numbers={"cell": float(r.v), "a": float(r.ea), "b": float(r.eb), "expected": float(r.exp), "overall": float(overall), "rows": int(r.rows), "fmt": t.fmt},
                               chart={"type": "bar", "title": f"{t.label}: this combination against its parts", "fmt": t.fmt, "unit": currency if t.money else "", "keep_order": True,
                                      "rows": [{"group": f"{a_} + {b_}", "value": float(r.v)}, {"group": f"all {a_}", "value": float(r.ea)}, {"group": f"all {b_}", "value": float(r.eb)}, {"group": "everything", "value": float(overall)}],
                                      "focus": f"{a_} + {b_}"},
                               evidence=rows_sample(F, mask, [c1, c2, t.num] + [c for c in ("order_id", "revenue") if c in F.df.columns], sort_col="revenue" if "revenue" in F.df.columns else None),
                               source=F.name, tags=[c1, a_, c2, b_, "combination"]))
    return apply_bh(out)

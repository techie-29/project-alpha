"""Open exploration: no checklist. For each measure, search combinations of two groups for cells that behave very
differently from what each group alone would predict (e.g. returns are 3x for warehouse X + Economy shipping).

Because the most extreme cell is picked out of many, its shuffle-test p-value is multiplied by the number of cells
searched in that pair (Bonferroni), so random noise in big tables does not pass."""
from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
from .common import insight, perm_group_test, apply_bh, codes_of, fmt_value, rows_sample, leaks
from .targets import targets, group_columns
from .groups import material, _group_series

MIN_CELL = 40


def _codes(F, col, m):
    s = _group_series(F.df[col]).astype("string").fillna("?")
    c, u = pd.factorize(s[m], sort=False)
    return c, np.asarray(u, dtype=object)


def run(F, currency: str | None, max_cols: int = 8, max_tests: int = 40) -> list[dict]:
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
        tcols = [c for c in cols if not (t.kind == "rate" and leaks(num[m], F.df[c][m]))]
        N, D = num[m], den[m]
        overall = N.sum() / D.sum()
        positive = overall > 0 and (N >= 0).all()
        codes = {c: _codes(F, c, m) for c in tcols}
        cand = []
        for c1, c2 in itertools.combinations(tcols, 2):
            (a, ua), (b, ub) = codes[c1], codes[c2]
            ka, kb = len(ua), len(ub)
            cell = a * kb + b
            cn = np.bincount(cell, weights=N, minlength=ka * kb); cd = np.bincount(cell, weights=D, minlength=ka * kb); cr = np.bincount(cell, minlength=ka * kb)
            an = np.bincount(a, weights=N, minlength=ka); ad = np.bincount(a, weights=D, minlength=ka)
            bn = np.bincount(b, weights=N, minlength=kb); bd = np.bincount(b, weights=D, minlength=kb)
            with np.errstate(divide="ignore", invalid="ignore"):
                v = cn / cd; ea = np.repeat(an / ad, kb); eb = np.tile(bn / bd, ka)
            exp = ea * eb / overall if positive else ea + eb - overall
            ok = (cr >= MIN_CELL) & np.isfinite(v)
            n_cells = int(ok.sum())
            if n_cells < 4:
                continue
            gap = np.where(ok, np.abs(v - exp), -1)
            for j in np.argsort(-gap)[:2]:
                if gap[j] <= 0:
                    continue
                up = v[j] >= overall
                beyond = v[j] > max(ea[j], eb[j], exp[j]) if up else v[j] < min(ea[j], eb[j], exp[j])
                if beyond and material(t, v[j], exp[j]) and material(t, v[j], overall):
                    cand.append((gap[j] * np.sqrt(cr[j]), c1, c2, ua[j // kb], ub[j % kb], float(v[j]), float(ea[j]), float(eb[j]), float(exp[j]), int(cr[j]), n_cells))
        for score, c1, c2, va, vb, cv, cea, ceb, cexp, rows, n_cells in sorted(cand, key=lambda x: -x[0])[:3]:
            if tests >= max_tests:
                break
            tests += 1
            ps = []
            for col_in, val_in, col_other, val_other in ((c1, va, c2, vb), (c2, vb, c1, va)):
                ci, ui = codes[col_in]
                inside_local = ci == int(np.where(ui == val_in)[0][0])
                co, uo = codes[col_other]
                sub = co[inside_local]
                j = int(np.where(uo == val_other)[0][0])
                _, p = perm_group_test(N[inside_local], D[inside_local], sub, len(uo), B1=199, B2=1999)
                ps.append(float(p[j]))
            p = min(1.0, max(ps) * n_cells)                 # corrected for picking the most extreme of n_cells
            up = cv > overall
            good = bool((t.polarity > 0) == bool(up)) if t.polarity else None
            a_, b_ = str(va), str(vb)
            head = f"{t.label} is {'especially high' if up else 'especially low'} for {a_} + {b_}"
            det = (f"{fmt_value(cv, t.fmt, (F.duration_unit if t.fmt == 'days' else currency or ''))} for {c1.replace('_', ' ')} {a_} with {c2.replace('_', ' ')} {b_} ({rows:,} rows), "
                   f"against {fmt_value(cea, t.fmt, (F.duration_unit if t.fmt == 'days' else currency or ''))} for all of {a_}, {fmt_value(ceb, t.fmt, (F.duration_unit if t.fmt == 'days' else currency or ''))} for all of {b_}, and {fmt_value(overall, t.fmt, (F.duration_unit if t.fmt == 'days' else currency or ''))} overall. "
                   f"The two together would suggest about {fmt_value(cexp, t.fmt, (F.duration_unit if t.fmt == 'days' else currency or ''))}, so this combination stands out on its own.")
            mask = pd.Series(m, index=F.df.index) & (_group_series(F.df[c1]).astype("string") == a_) & (_group_series(F.df[c2]).astype("string") == b_)
            out.append(insight("combination", "operations" if t.kind == "rate" else "sales", head, det, p=p,
                               polarity="good" if good else ("bad" if good is False else "neutral"), actionable=True,
                               look_at={"col": c1, "value": a_, "col2": c2, "value2": b_}, metric=t.id, metric_label=t.label,
                               numbers={"cell": cv, "a": cea, "b": ceb, "expected": cexp, "overall": float(overall), "rows": rows, "cells_searched": n_cells, "fmt": t.fmt},
                               chart={"type": "bar", "title": f"{t.label}: this combination against its parts", "fmt": t.fmt, "unit": currency if t.money else "", "keep_order": True,
                                      "rows": [{"group": f"{a_} + {b_}", "value": cv}, {"group": f"all {a_}", "value": cea}, {"group": f"all {b_}", "value": ceb}, {"group": "everything", "value": float(overall)}],
                                      "focus": f"{a_} + {b_}"},
                               evidence=rows_sample(F, mask, [c1, c2, t.num] + [c for c in ("order_id", "revenue") if c in F.df.columns], sort_col="revenue" if "revenue" in F.df.columns else None),
                               source=F.name, tags=[c1, a_, c2, b_, "combination"]))
    return apply_bh(out)

"""Stage 4: assemble the report the website shows: Briefing -> Your Data -> Insights -> Intelligence.
Everything here is arithmetic and wording templates; the language model (Stage 3) can only add to it, never replace numbers."""
from __future__ import annotations
import datetime as dt
import re
import numpy as np
import pandas as pd
from ..scan.engine import ScanResult
from ..discover.discover import pretty, fmt, polarity
from ..understand.prepare import Prepared

RECENT = {"day": 28, "week": 4, "month": 3}
HINT_COLS = re.compile(r"(channel|region|country|categor|segment|method|type|state|brand|city|warehouse|campaign|status)", re.I)


def clean(o):
    """Make anything JSON-safe: numpy -> python, NaN/inf -> None, Timestamps -> ISO text."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def _pct_change(new: float, old: float):
    return None if (old is None or not np.isfinite(old) or old == 0 or new is None or not np.isfinite(new)) else (new - old) / abs(old)


def _window_sum(raw: np.ndarray, end: int, n: int):
    seg = raw[max(0, end - n):end]
    return float(np.nansum(seg)) if np.isfinite(seg).any() else None


def _window_mean(raw: np.ndarray, end: int, n: int):
    seg = raw[max(0, end - n):end]
    return float(np.nanmean(seg)) if np.isfinite(seg).any() else None


# ---------------- Your Data ----------------
def your_data(p: Prepared, sr: ScanResult) -> dict:
    ctx, ax = sr.ctx, sr.axis
    T, R = ax.T, RECENT[ax.step]
    kpis, series = [], []
    money_names = [n for n, s in sr.overall.items() if s.kind == "money" and sr.measures[n].col == p.money_col]
    money_names.sort(key=lambda n: -float(np.nansum(sr.overall[n].raw)))
    for n in money_names[:3]:
        s, m = sr.overall[n], sr.measures[n]
        cur = m.currency or ""
        total = float(np.nansum(s.raw))
        rc, pv = _window_sum(s.raw, T, R), _window_sum(s.raw, T - R, R)
        yoy = None
        if T >= 2 * ax.per_year:
            yoy = _pct_change(_window_sum(s.raw, T, ax.per_year), _window_sum(s.raw, T - ax.per_year, ax.per_year))
        mk = ctx.mask(m)
        kpis.append({"label": pretty(n), "kind": "money", "value": total, "unit": cur, "recent": rc, "previous": pv,
                     "change_recent": _pct_change(rc, pv), "change_year": yoy, "rows": int(mk.sum()),
                     "per_row": float(ctx.vector(m)[mk].sum() / max(mk.sum(), 1)), "spark": [None if not np.isfinite(x) else float(x) for x in s.raw[-52:]],
                     "recent_label": f"last {R} {ax.step}s vs the {R} before"})
        series.append({"name": pretty(n), "unit": cur, "labels": [ax.label(i) for i in range(T)], "values": [None if not np.isfinite(x) else float(x) for x in s.raw]})
    if "rows" in sr.overall:
        s = sr.overall["rows"]
        kpis.append({"label": "Rows that count", "kind": "count", "value": float(np.nansum(s.raw)), "unit": "", "recent": _window_sum(s.raw, T, R),
                     "previous": _window_sum(s.raw, T - R, R), "change_recent": _pct_change(_window_sum(s.raw, T, R), _window_sum(s.raw, T - R, R)),
                     "change_year": _pct_change(_window_sum(s.raw, T, ax.per_year), _window_sum(s.raw, T - ax.per_year, ax.per_year)) if T >= 2 * ax.per_year else None,
                     "spark": [None if not np.isfinite(x) else float(x) for x in s.raw[-52:]], "recent_label": f"last {R} {ax.step}s vs the {R} before"})
    profit = next((n for n in sr.overall if re.match(r"profit", n, re.I) and money_names and (sr.measures[n].currency == sr.measures[money_names[0]].currency)), None)
    if profit and money_names:
        mt, pt = float(np.nansum(sr.overall[money_names[0]].raw)), float(np.nansum(sr.overall[profit].raw))
        if mt:
            kpis.append({"label": "Profit margin", "kind": "rate", "value": pt / mt, "unit": "", "note": f"profit {fmt(pt, 'money', 'sum', sr.measures[profit].currency or '')} on sales {fmt(mt, 'money', 'sum', sr.measures[money_names[0]].currency or '')}"})
    for n, s in sr.overall.items():
        if s.agg == "rate" and len([k for k in kpis if k["kind"] == "rate"]) < 5:
            rc, pv = _window_mean(s.raw, T, R), _window_mean(s.raw, T - R, R)
            kpis.append({"label": pretty(n), "kind": "rate", "value": float(np.nanmean(s.raw)), "unit": "", "recent": rc, "previous": pv,
                         "change_recent": None if (rc is None or pv is None) else rc - pv, "change_is_points": True,
                         "spark": [None if not np.isfinite(x) else float(x) for x in s.raw[-52:]], "recent_label": f"last {R} {ax.step}s vs the {R} before"})
    # --- breakdowns of the biggest money measure ---
    breakdowns = []
    if money_names:
        m = sr.measures[money_names[0]]
        v, mk = ctx.vector(m), ctx.mask(m)
        cols = [c for c in p.slices if 2 <= p.roles.get(c, {}).get("unique", 99) <= 30 and c != p.currency_col and c != m.col]
        cols.sort(key=lambda c: (0 if HINT_COLS.search(c) else 1, p.roles[c].get("unique", 99)))
        last_year = (ctx.idx >= T - ax.per_year) if T >= 2 * ax.per_year else None
        prev_year = ((ctx.idx >= T - 2 * ax.per_year) & (ctx.idx < T - ax.per_year)) if T >= 2 * ax.per_year else None
        for col in cols[:6]:
            codes, uniq = ctx.codes(col)
            sel = mk & (codes >= 0)
            sums = np.bincount(codes[sel], weights=v[sel], minlength=len(uniq))
            cnts = np.bincount(codes[sel], minlength=len(uniq))
            tot = sums.sum()
            if tot <= 0:
                continue
            ch = None
            if last_year is not None:
                a = np.bincount(codes[sel & last_year], weights=v[sel & last_year], minlength=len(uniq))
                b = np.bincount(codes[sel & prev_year], weights=v[sel & prev_year], minlength=len(uniq))
                ch = (a, b)
            order = np.argsort(-sums)[:8]
            breakdowns.append({"column": col, "measure": pretty(m.name), "unit": m.currency or "", "rows": [
                {"value": str(uniq[i]), "amount": float(sums[i]), "share": float(sums[i] / tot), "rows": int(cnts[i]),
                 "change_year": None if ch is None else _pct_change(float(ch[0][i]), float(ch[1][i]))} for i in order if cnts[i] > 0]})
    # --- outcomes (status) and weekday rhythm ---
    outcomes = None
    status_col = next((c for c in p.slices if re.search(r"status|state|outcome", c, re.I) and 2 <= p.roles.get(c, {}).get("unique", 99) <= 12 and re.search(r"order|status$", c, re.I)), None)
    if status_col:
        vc = p.df[status_col].astype(str).where(p.df[status_col].notna()).value_counts()
        outcomes = {"column": status_col, "rows": [{"value": k, "count": int(c), "share": float(c / vc.sum())} for k, c in vc.items()]}
    weekday = None
    if money_names and ax.step in ("day", "week"):
        m = sr.measures[money_names[0]]
        v, mk = ctx.vector(m), ctx.mask(m)
        t = p.df["_t"]
        wd = t.dt.weekday.fillna(-1).astype(int).values
        sel = mk & (wd >= 0)
        sums = np.bincount(wd[sel], weights=v[sel], minlength=7)
        n_days = pd.Series(1, index=pd.date_range(t.min().normalize(), t.max().normalize())).groupby(lambda d: d.weekday()).sum().reindex(range(7)).fillna(1).values
        weekday = {"unit": m.currency or "", "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "values": [float(x) for x in sums / n_days], "measure": pretty(m.name)}
    return {"view": p.name, "sources": p.sources or [p.name], "step": ax.step, "periods": T,
            "from": ax.starts[0].isoformat(), "to": ax.starts[-1].isoformat(), "rows_total": int(len(p.df)),
            "rows_counted": int(p.ok.sum()) if p.ok is not None else int(len(p.df)), "kpis": kpis, "series": series, "breakdowns": breakdowns,
            "outcomes": outcomes, "weekday": weekday, "notes": p.notes + sr.axis.notes, "warnings": p.warnings}


# ---------------- evidence rows ----------------
def evidence_sample(sr: ScanResult, f: dict, limit: int = 60) -> dict:
    ctx, p = sr.ctx, sr.ctx.p
    m = sr.measures.get(f["evidence"]["measure"])
    if m is None:
        return {"total": 0, "rows": []}
    mk = ctx.mask(m) if m.agg != "rate" else ((ctx.idx >= 0) & (ctx.ok if m.scope == "ok" else True))
    if m.currency:
        mk &= ctx.cur == m.currency
    t0, t1 = pd.Timestamp(f["evidence"]["from"]), pd.Timestamp(f["evidence"]["to"])
    t = p.df["_t"]
    mk &= ((t >= t0) & (t <= t1)).values
    for flt in f["evidence"]["filters"]:
        codes, uniq = ctx.codes(flt["col"])
        hit = np.where(uniq == flt["val"])[0]
        mk &= np.isin(codes, hit)
    if m.agg == "rate":
        mk &= p.df[m.flag_col].values.astype(bool)
    idx = np.nonzero(mk)[0]
    key = ctx.vector(m)[idx] if m.agg in ("sum", "count", "mean") else np.zeros(len(idx))
    order = idx[np.argsort(-np.abs(key))][:limit] if m.agg in ("sum", "mean") else idx[:limit]
    cols = ["_row", p.time_col if p.time_col in p.df.columns else "_t"] + ([m.col] if m.col else []) + [fl["col"] for fl in f["evidence"]["filters"]]
    extra = [c for c in p.slices if c not in cols][:3] + [c for c, i in p.roles.items() if i["role"] == "id" and c not in cols][:1]
    cols = [c for c in dict.fromkeys(cols + extra) if c in p.df.columns]
    sub = p.df.loc[order, cols]
    return {"file": (p.sources or [p.name])[0], "total": int(len(idx)), "columns": ["source row" if c == "_row" else c for c in cols], "rows": clean(sub.astype(object).where(sub.notna(), None).values.tolist())}


# ---------------- Intelligence + Briefing ----------------
def _action_line(f: dict) -> str:
    d = f.get("drivers")
    if d and d["by_column"]:
        b = d["by_column"][0]; t = b["top"][0]
        sur = f" (about {t['surprise']:.0f}x its usual weight)" if t.get("surprise") and t["surprise"] >= 2 else ""
        return f"Look at {t['value']} ({b['col'].replace('_', ' ')}) first: it accounts for {t['share_of_change']:.0%} of the change{sur}."
    if f["slice_col"]:
        return f"Look at the rows for {f['slice_val']} ({f['slice_col'].replace('_', ' ')}) in {f['when']}."
    return f"Open the rows behind this for {f['when']} to see what the period had in common."


def intelligence(findings: list[dict]) -> dict:
    fix, keep, watch = [], [], []
    for f in findings:
        item = {"finding_id": f["id"], "title": f["title"], "why": f["detail"], "where_to_look": _action_line(f), "level": f["level"],
                "claim": f["claim"], "impact_share": f["numbers"]["impact_share"], "story": f.get("story")}
        if f["level"] == "confirmed" and f["polarity"] == "bad":
            item["bucket_note"] = "Worth fixing: a confirmed change that hurts."
            fix.append(item)
        elif f["level"] == "confirmed" and f["polarity"] == "good":
            item["bucket_note"] = "Worth keeping: a confirmed change that helps. Worth understanding so it lasts."
            keep.append(item)
        else:
            item["bucket_note"] = "Keep watching: an early sign, or a change that is not clearly good or bad."
            watch.append(item)
    return {"fix": fix[:10], "keep": keep[:10], "watch": watch[:12]}


def briefing(files: list[dict], views_out: list[dict], disc: list[dict], reading: dict) -> dict:
    all_f = [f for d in disc for f in d["findings"]]
    all_f.sort(key=lambda f: (0 if f["level"] == "confirmed" else 1, -(f["numbers"]["impact_share"] or 0), f["q"]))
    conf = [f for f in all_f if f["level"] == "confirmed"]
    early = [f for f in all_f if f["level"] != "confirmed"]
    tested = sum(d["checked"]["tests"] for d in disc)
    series = sum(d["checked"]["series"] for d in disc)
    if conf:
        headline = conf[0]["title"] + "."
        status = f"{len(conf)} confirmed change{'s' if len(conf) != 1 else ''} and {len(early)} early sign{'s' if len(early) != 1 else ''} found."
    elif early:
        headline = "No confirmed changes. A few early signs are worth watching."
        status = f"{len(early)} early sign{'s' if len(early) != 1 else ''}, nothing confirmed."
    else:
        headline = "Nothing unusual changed in the period checked."
        status = "Everything checked stayed within its own normal range."
    vd = views_out[0] if views_out else None
    coverage = None
    if vd:
        coverage = (f"{vd['rows_total']:,} rows from {vd['from'][:10]} to {vd['to'][:10]}, looked at {vd['step']} by {vd['step']}; "
                    f"{vd['rows_counted']:,} rows count toward amounts.")
    stories = []
    seen = set()
    for f in all_f:
        key = (f["view"], f.get("story"))
        if key in seen:
            continue
        seen.add(key)
        stories.append({"finding_id": f["id"], "title": f["title"], "detail": f["detail"], "level": f["level"], "claim": f["claim"],
                        "polarity": f["polarity"], "evidence_strength": f["evidence_strength"], "action": _action_line(f),
                        "impact_share": f["numbers"]["impact_share"], "more": len(f["folded"])})
        if len(stories) >= 5:
            break
    caveats = []
    for v in views_out:
        caveats += v["warnings"][:4]
    unsure = [c for fl in reading["files"] for c in fl["columns"] if c["needs_confirmation"] and c["role"] not in ("empty", "constant")]
    if unsure:
        caveats.append(f"{len(unsure)} column(s) were read with low confidence. Findings that depend on them are less certain until you confirm how they were read.")
    return {"headline": headline, "status": status, "coverage": coverage, "stories": stories, "caveats": caveats[:8],
            "checked": {"files": len(files), "series": series, "tests": tested},
            "what_this_means": "Each finding is a calculated change with a strength label; none is claimed as a cause."}


def questions(findings: list[dict]) -> list[dict]:
    out = []
    for f in findings[:8]:
        d = f.get("drivers")
        if f["level"] == "confirmed" and (not d or d["not_explained"] > 0.3 or not d["by_column"]):
            out.append({"id": f["id"], "finding_id": f["id"],
                        "text": f"{f['title']}. Did anything change around {f['when']} that the data would not show (a price change, a campaign, stock or staffing problems, a closure)?"})
    return out[:6]

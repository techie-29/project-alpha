"""Stage 2b: turn leads into findings. Merge duplicates, find what drives a change ("surprise" = share of the change
divided by the normal share), measure money impact, tag seasonal repeats, group into stories. Never says 'caused'."""
from __future__ import annotations
import hashlib
import re
import numpy as np
import pandas as pd
from ..scan.engine import ScanResult, ViewContext, family_of
from ..understand.prepare import MIN_SLICE_ROWS

GOOD_UP = re.compile(r"(sales|revenue|profit|rows|quantity|units|rating|score|margin|loyalty|orders|visits|income)", re.I)
BAD_UP = re.compile(r"(rate of .*(cancel|return|refund|fail|declin|reject)|delivery_days|delay|late|complaint|churn|defect)", re.I)
BAD_UP_ALSO = re.compile(r"(^|_)(days)$", re.I)


# ---------- wording helpers ----------
def pretty(measure: str) -> str:
    m = measure
    if m.startswith("share of "):
        return "Share of " + pretty(m[9:])
    if m.startswith("rate of "):
        body = m[8:]
        mm = re.match(r"^(\w+) = (.+)$", body)
        if mm:
            return f"{mm.group(2)} rate ({mm.group(1).replace('_', ' ')})"
        return body.replace("_", " ") + " rate"
    cur = ""
    mm = re.match(r"^(.*) \[([A-Z]{3})\]$", m)
    if mm:
        m, cur = mm.group(1), mm.group(2)
    t = m.replace("_", " ").strip()
    t = t[:1].upper() + t[1:]
    return f"{t} ({cur})" if cur else t


def polarity(measure: str) -> str:
    base = family_of(measure)
    if BAD_UP.search(base) or BAD_UP_ALSO.search(base):
        return "bad_up"
    if re.search(r"(cost|discount|tax|shipping|age|price|points)", base, re.I):
        return "neutral"
    if GOOD_UP.search(base):
        return "good_up"
    return "neutral"


def fmt(v: float | None, kind: str, agg: str, cur: str = "") -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    if agg == "rate" or kind == "share":
        return f"{v * 100:.1f}%"
    a = abs(v)
    s = f"{v:,.0f}" if a >= 100 else (f"{v:,.1f}" if a >= 10 else f"{v:,.2f}")
    return f"{cur} {s}".strip() if kind == "money" else s


def _ids(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


# ---------- windows ----------
def windows(lead: dict, T: int):
    a, b = lead["a"], lead["b"]
    if lead["test"] == "shift":
        return np.arange(a, b + 1), np.arange(0, a)
    if lead["test"] == "window":
        focus = np.arange(a, b + 1)
        return focus, np.setdiff1d(np.arange(T), focus)
    if lead["test"] == "trend":
        third = max(3, T // 3)
        return np.arange(T - third, T), np.arange(0, third)
    focus = np.array([a])
    return focus, np.setdiff1d(np.arange(T), focus)


# ---------- drivers ----------
def drivers(ctx: ViewContext, m, focus: np.ndarray, base: np.ndarray, skip_col: str | None = None) -> dict | None:
    T = ctx.ax.T
    v, mk = ctx.vector(m), ctx.mask(m)
    fm, bm = np.zeros(T, bool), np.zeros(T, bool)
    fm[focus], bm[base] = True, True
    rowsF = mk & fm[ctx.idx.clip(0)]
    rowsB = mk & bm[ctx.idx.clip(0)]
    nF, nB = max(len(focus), 1), max(len(base), 1)
    if rowsF.sum() < 3 or rowsB.sum() < 3:
        return None
    additive = m.agg in ("sum", "count")
    if additive:
        total = v[rowsF].sum() / nF - v[rowsB].sum() / nB
    else:
        total = v[rowsF].mean() - v[rowsB].mean()
    if not np.isfinite(total) or abs(total) < 1e-12:
        return None
    sign = 1.0 if total > 0 else -1.0
    cols_out = []
    for col in ctx.p.slices:
        if col == m.col or col == skip_col or (m.currency and col == ctx.p.currency_col) or (m.flag_col and m.flag_col.startswith(f"__rate__{col}")):
            continue
        codes, uniq = ctx.codes(col)
        K = len(uniq)
        okF, okB = rowsF & (codes >= 0), rowsB & (codes >= 0)
        cF = np.bincount(codes[okF], minlength=K).astype(float)
        cB = np.bincount(codes[okB], minlength=K).astype(float)
        sF = np.bincount(codes[okF], weights=v[okF], minlength=K)
        sB = np.bincount(codes[okB], weights=v[okB], minlength=K)
        if (cF + cB).sum() == 0 or ((cF + cB) >= MIN_SLICE_ROWS).sum() < 2:
            continue
        if additive:
            c = sF / nF - sB / nB
            normal = sB / max(sB.sum(), 1e-12)
            rate_part = mix_part = None
        else:
            wF, wB = cF / max(cF.sum(), 1), cB / max(cB.sum(), 1)
            with np.errstate(invalid="ignore", divide="ignore"):
                mF, mB = sF / cF, sB / cB
            mF = np.where(cF > 0, mF, np.where(cB > 0, mB, 0.0)); mB = np.where(cB > 0, mB, mF)
            wbar, mbar = (wF + wB) / 2, (mF + mB) / 2
            base_mean = v[rowsB].mean()
            rate_part = wbar * (mF - mB)
            mix_part = (wF - wB) * (mbar - base_mean)
            c = rate_part + mix_part
            normal = wB
        tot_c = c.sum()
        if abs(tot_c) < 1e-12 or np.sign(tot_c) != sign:
            continue
        share = c / tot_c
        enough = (cF + cB) >= MIN_SLICE_ROWS
        order = [i for i in np.argsort(-share) if enough[i] and share[i] > 0][:5]
        if not order:
            continue
        top = []
        for i in order:
            sur = share[i] / normal[i] if normal[i] > 1e-9 else None
            top.append({"col": col, "value": str(uniq[i]), "share_of_change": float(share[i]), "normal_share": float(normal[i]),
                        "surprise": None if sur is None else float(sur), "change": float(c[i] * (1 if additive else 1)),
                        "rate_effect": None if rate_part is None else float(rate_part[i]), "mix_effect": None if mix_part is None else float(mix_part[i])})
        cols_out.append({"col": col, "explained": float(min(1.0, sum(t["share_of_change"] for t in top[:3]))), "top": top,
                         "rate_share": None if rate_part is None else float(rate_part.sum() / tot_c),
                         "mix_share": None if mix_part is None else float(mix_part.sum() / tot_c)})
    if not cols_out:
        return None
    cols_out.sort(key=lambda d: -d["explained"])
    best = cols_out[0]
    return {"total_change": float(total), "by_column": cols_out[:4], "explained": best["explained"], "not_explained": float(max(0.0, 1 - best["explained"]))}


# ---------- seasonal repeat ----------
def recurs_yearly(sr: ScanResult, lead: dict) -> bool:
    ax = sr.axis
    short_shift = lead["test"] == "shift" and (lead["b"] - lead["a"] + 1) <= ax.per_year // 3
    if ax.seasonal or ax.T < 2 * ax.per_year or not (lead["test"] in ("window", "outlier") or short_shift):
        return False
    s = sr.series.get(lead["sid"])
    if s is None:
        return False
    raw, a, b = s.raw, lead["a"], lead["b"]
    inside = np.zeros(len(raw), bool); inside[a:b + 1] = True
    base = np.nanmean(raw[~inside])
    d0 = np.nanmean(raw[a:b + 1]) - base
    if not np.isfinite(d0) or d0 == 0:
        return False
    for k in range(-3, 4):
        if k == 0:
            continue
        o = k * ax.per_year
        lo, hi = a + o, b + o
        if lo < 0 or hi >= len(raw):
            continue
        d1 = np.nanmean(raw[lo:hi + 1]) - base
        if np.isfinite(d1) and np.sign(d1) == np.sign(d0) and abs(d1) >= 0.5 * abs(d0):
            return True
    return False


# ---------- main ----------
def discover(sr: ScanResult) -> dict:
    ctx, ax, p = sr.ctx, sr.axis, sr.ctx.p
    T = ax.T
    # 1. one lead per series (best q), others recorded as supporting tests
    best: dict[int, dict] = {}
    for l in sorted(sr.leads, key=lambda d: d["q"]):
        if l["sid"] not in best:
            best[l["sid"]] = {**l, "also": []}
        else:
            best[l["sid"]]["also"].append(l["test"])
    leads = list(best.values())
    seasonal, active = [], []
    for l in leads:
        (seasonal if recurs_yearly(sr, l) else active).append(l)

    # money reference for impact
    top_money = next((m for m in sr.measures.values() if m.col == p.money_col and m.kind == "money" and m.name in sr.overall), None)
    avg_money_per_row = total_money = None
    if top_money is not None:
        mk = ctx.mask(top_money); vv = ctx.vector(top_money)
        total_money = float(vv[mk].sum()); avg_money_per_row = total_money / max(int(mk.sum()), 1)

    findings = []
    for l in active:
        m = sr.measures.get(family_of(l["measure"]) if l["measure"] not in sr.measures else l["measure"])
        s = sr.series.get(l["sid"])
        base_name = l["measure"][9:] if l["measure"].startswith("share of ") else l["measure"]
        m = sr.measures.get(base_name) or m
        focus, base = windows(l, T)
        raw = s.raw if s is not None else None
        impact = exposure = None
        cur = m.currency if m is not None and m.currency else ""
        if raw is not None and l["kind"] == "money" and l["agg"] == "sum":
            fv, bv = raw[focus], raw[base]
            impact = float(np.nansum(fv) - np.nanmean(bv) * np.isfinite(fv).sum()) if np.isfinite(bv).any() else None
        elif raw is not None and l["agg"] == "count":
            fv, bv = raw[focus], raw[base]
            impact = float(np.nansum(fv) - np.nanmean(bv) * np.isfinite(fv).sum())
        elif raw is not None and l["agg"] == "rate" and avg_money_per_row is not None:
            rf, rb = np.nanmean(raw[focus]), np.nanmean(raw[base])
            rows = float(np.nansum(s.cnt[focus]))
            exposure = float((rf - rb) * rows * avg_money_per_row)
        denom = None
        if l["kind"] == "money" and raw is not None:
            ov = sr.overall.get(l["measure"])
            denom = float(np.nansum(np.abs(ov.raw))) if ov is not None else None
        elif l["agg"] == "count":
            ov = sr.overall.get(l["measure"]); denom = float(np.nansum(ov.raw)) if ov is not None else None
        elif exposure is not None and total_money:
            denom = total_money
        mag = impact if impact is not None else exposure
        impact_share = abs(mag) / denom if (mag is not None and denom) else None

        drv = None
        if l["slice_col"] is None and m is not None and l["test"] != "outlier" and l["kind"] != "share":
            drv = drivers(ctx, m, focus, base)
        up = l["delta"] > 0
        pol = "neutral" if l["kind"] == "share" else polarity(l["measure"])
        good = (pol == "good_up" and up) or (pol == "bad_up" and not up)
        bad = (pol == "good_up" and not up) or (pol == "bad_up" and up)
        kind, agg = l["kind"], l["agg"]
        when = ax.span_label(l["a"], l["b"])
        scope = "" if l["slice_col"] is None else f" for {l['slice_val']} ({l['slice_col'].replace('_', ' ')})"
        label = pretty(l["measure"])
        before_s, after_s = fmt(l["before"], kind, agg, cur), fmt(l["after"], kind, agg, cur)
        if l["test"] == "shift":
            title = f"{label}{scope} {'rose' if up else 'fell'} from {ax.label(l['a'])} onward"
            detail = f"Average per {ax.step} was {before_s} before and {after_s} after."
        elif l["test"] == "window":
            title = f"{label}{scope} was unusually {'high' if up else 'low'} from {when}"
            detail = f"Average per {ax.step} was {after_s} in that stretch versus {before_s} otherwise."
        elif l["test"] == "trend":
            title = f"{label}{scope} {'rose' if up else 'fell'} steadily over {ax.label(0)} to {ax.label(T - 1)}"
            detail = f"Early average per {ax.step} {before_s}, recent average {after_s}."
        else:
            title = f"{label}{scope} {'spiked' if up else 'dipped'} in the {ax.step} of {ax.label(l['a'])}"
            detail = f"That {ax.step} was {after_s} against a typical {before_s}."
        filters = [] if l["slice_col"] is None else [{"col": l["slice_col"], "val": l["slice_val"]}]
        t_from = ax.starts[focus[0]]
        t_to = ax.starts[focus[-1]] + (pd.Timedelta(days=1) if ax.step == "day" else pd.Timedelta(days=7) if ax.step == "week" else pd.offsets.MonthBegin(1)) - pd.Timedelta(seconds=1)
        findings.append({
            "id": _ids(sr.view, l["measure"], l["slice_col"], l["slice_val"], l["test"], l["a"], l["b"]),
            "view": sr.view, "title": title, "detail": detail,
            "level": l["level"], "claim": "Supported by evidence" if l["level"] == "confirmed" else "Possible (early sign)",
            "evidence_strength": "very sure" if l["q"] <= 0.001 else ("sure" if l["q"] <= 0.05 else "early sign"),
            "measure": l["measure"], "label": label, "family": l["family"], "kind": kind, "agg": agg, "currency": cur or None,
            "slice_col": l["slice_col"], "slice_val": l["slice_val"], "test": l["test"], "also_tests": l["also"],
            "p": l["p"], "q": l["q"], "when": when, "step": ax.step,
            "a": int(l["a"]), "b": int(l["b"]),
            "numbers": {"before": l["before"], "after": l["after"], "delta": l["delta"], "relative": l["rel"], "impact": impact, "exposure": exposure,
                        "impact_share": impact_share, "unit": cur},
            "direction": "up" if up else "down", "polarity": "good" if good else ("bad" if bad else "neutral"),
            "drivers": drv, "children": [], "folded": [],
            "evidence": {"view": sr.view, "from": t_from.isoformat(), "to": pd.Timestamp(t_to).isoformat(), "filters": filters,
                         "ok_only": bool(m is not None and m.scope == "ok"), "currency": cur or None, "measure": base_name},
            "chart": {"labels": [ax.label(i) for i in range(T)], "values": [None if not np.isfinite(x) else float(x) for x in (raw if raw is not None else [])],
                      "focus": [int(focus[0]), int(focus[-1])]},
            "caveats": [n for n in ax.notes if "Less than two" in n or "Two years" in n] + (["Based on very few rows per " + ax.step + ", so this can only be an early sign."] if l.get("sparse") else []),
        })

    # 2. fold slice findings into the overall finding of the same family when they overlap and agree
    overall = [f for f in findings if f["slice_col"] is None]
    keep = []
    for f in findings:
        host = None
        if f["slice_col"] is not None and f["kind"] != "share":
            for o in overall:
                if o["family"] == f["family"] and o["currency"] == f["currency"] and o["direction"] == f["direction"] and not (f["b"] < o["a"] or f["a"] > o["b"]):
                    host = o; break
        if host is not None:
            host["folded"].append({"id": f["id"], "title": f["title"], "q": f["q"], "slice_col": f["slice_col"], "slice_val": f["slice_val"]})
        else:
            keep.append(f)
    findings = keep

    # 3. rank: confirmed first, then size of money impact, then strength
    def rank(f):
        return (0 if f["level"] == "confirmed" else 1, -(f["numbers"]["impact_share"] or 0), f["q"])
    findings.sort(key=rank)

    # 4. stories: findings that overlap in time and share a family or a slice/driver value
    def keys(f):
        k = {("fam", f["family"])} if f["slice_col"] is None else set()
        if f["slice_col"]:
            k.add((f["slice_col"], f["slice_val"]))
        for d in (f["drivers"] or {}).get("by_column", [])[:1]:
            for t in d["top"][:2]:
                k.add((t["col"], t["value"]))
        return k
    parent = list(range(len(findings)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            fi, fj = findings[i], findings[j]
            if fi["test"] == "trend" or fj["test"] == "trend" or fi["b"] < fj["a"] or fj["b"] < fi["a"]:
                continue
            if keys(fi) & keys(fj):
                parent[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for i in range(len(findings)):
        groups.setdefault(find(i), []).append(i)
    stories = []
    for n, (root, members) in enumerate(sorted(groups.items(), key=lambda kv: min(kv[1]))):
        fs = [findings[i] for i in members]
        for f in fs:
            f["story"] = n
        stories.append({"id": n, "headline": fs[0]["id"], "finding_ids": [f["id"] for f in fs], "size": len(fs)})
    seasonal_out = [{"measure": pretty(l["measure"]), "scope": None if l["slice_col"] is None else f"{l['slice_val']} ({l['slice_col']})",
                     "when": ax.span_label(l["a"], l["b"]), "note": "Repeats at the same time every year, so it looks seasonal rather than a one-off change."} for l in seasonal][:15]
    return {"view": sr.view, "findings": findings, "stories": stories, "seasonal": seasonal_out,
            "checked": {"series": sr.n_series, "tests": sr.n_tests, "leads": len(sr.leads), "findings": len(findings), "seconds": round(sr.seconds, 1)},
            "axis_notes": sr.axis.notes, "dropped_duplicates": sr.dropped_duplicates}

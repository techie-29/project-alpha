"""Stage 2: scan every measure x slice x time window against its own history. No hand-set business thresholds."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from ..understand.prepare import Prepared, Measure, MIN_SLICE_ROWS
from .axis import Axis, build_axis, deseason, MIN_PERIODS
from .stats import run_tests, bh

MIN_ROWS_PER_PERIOD = 3          # hand-set statistical minimum (documented limit)
TOP_SLICE_VALUES = 40
MAX_MEASURES = 30
DUP_CORR = 0.9
CONFIRMED_Q, EARLY_Q = 0.05, 0.10
MIN_CONFIRM_ROWS = 5       # a series resting on fewer rows per period than this can only ever be an 'early sign'


@dataclass
class SeriesRec:
    sid: int
    measure: str
    family: str
    kind: str
    agg: str
    slice_col: str | None
    slice_val: str | None
    raw: np.ndarray
    cnt: np.ndarray


class ViewContext:
    """Row-level helpers shared by the scan and by discovery (so both use exactly the same rows)."""
    def __init__(self, p: Prepared, ax: Axis):
        self.p, self.ax, self.df, self.idx = p, ax, p.df, ax.idx
        self.ok = p.ok.values if p.ok is not None else np.ones(len(p.df), bool)
        self.cur = p.df[p.currency_col].astype(str).values if p.currency_col else None
        self._codes: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def codes(self, col: str):
        if col not in self._codes:
            c, u = pd.factorize(self.df[col].astype(str).where(self.df[col].notna()))
            self._codes[col] = (c, np.asarray(u))
        return self._codes[col]

    def vector(self, m: Measure) -> np.ndarray:
        return _vector(self.df, m)

    def mask(self, m: Measure) -> np.ndarray:
        mk = (self.idx >= 0) & (self.ok if m.scope == "ok" else True)
        if m.currency:
            mk = mk & (self.cur == m.currency)
        return mk & ~np.isnan(self.vector(m))


@dataclass
class ScanResult:
    view: str
    axis: Axis
    leads: list[dict]
    overall: dict[str, SeriesRec]
    n_series: int
    n_tests: int
    dropped_duplicates: list[str]
    seconds: float
    notes: list[str] = field(default_factory=list)
    ctx: object = None
    series: dict = field(default_factory=dict)      # sid -> SeriesRec for series that produced a lead
    measures: dict = field(default_factory=dict)    # measure name -> Measure


def family_of(name: str) -> str:
    return name.split(" [")[0]


def _finish(sums: np.ndarray, cnts: np.ndarray, agg: str) -> np.ndarray:
    if agg in ("sum", "count"):
        raw = sums.astype(float).copy()
        for r in range(raw.shape[0]):                       # outside the slice's own life it is "unknown", not zero
            nz = np.nonzero(cnts[r])[0]
            if len(nz):
                raw[r, :nz[0]] = np.nan
                raw[r, nz[-1] + 1:] = np.nan
            else:
                raw[r, :] = np.nan
        return raw
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = sums / cnts
    raw[cnts < MIN_ROWS_PER_PERIOD] = np.nan
    return raw


def _vector(df: pd.DataFrame, m: Measure) -> np.ndarray:
    if m.agg == "count":
        return np.ones(len(df))
    if m.agg == "rate":
        return df[m.flag_col].values.astype(float)
    return pd.to_numeric(df[m.col], errors="coerce").values.astype(float)


def scan_view(p: Prepared, view_name: str | None = None) -> ScanResult | None:
    t0 = time.time()
    if p.kind not in ("events", "periodic") or p.time_col is None or "_t" not in p.df.columns:
        return None
    ax = build_axis(p.df["_t"], p.kind == "periodic")
    if ax is None:
        return None
    df, T = p.df, ax.T
    idx = ax.idx
    ok = p.ok.values if p.ok is not None else np.ones(len(df), bool)
    cur = df[p.currency_col].astype(str).values if p.currency_col else None
    factor_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def codes_for(col: str):
        if col not in factor_cache:
            c, u = pd.factorize(df[col].astype(str).where(df[col].notna()))
            factor_cache[col] = (c, np.asarray(u))
        return factor_cache[col]

    def mask_of(m: Measure) -> np.ndarray:
        mk = (idx >= 0) & (ok if m.scope == "ok" else True)
        if m.currency:
            mk = mk & (cur == m.currency)
        return mk

    # ---- 1. overall series for every measure, then drop near-duplicates ----
    vec: dict[str, np.ndarray] = {}
    rec: list[tuple[Measure, SeriesRec]] = []
    sid = 0
    for m in p.measures:
        v = _vector(df, m); vec[m.name] = v
        mk = mask_of(m) & ~np.isnan(v)
        if mk.sum() < MIN_SLICE_ROWS:
            continue
        sums = np.bincount(idx[mk], weights=v[mk], minlength=T)[None, :]
        cnts = np.bincount(idx[mk], minlength=T)[None, :]
        raw = _finish(sums, cnts, m.agg)[0]
        if np.isfinite(raw).sum() < MIN_PERIODS or np.nanstd(raw) == 0:
            continue
        rec.append((m, SeriesRec(sid, m.name, family_of(m.name), m.kind, m.agg, None, None, raw, cnts[0]))); sid += 1
    if not rec:
        return None
    order = sorted(range(len(rec)), key=lambda i: (rec[i][0].col != p.money_col, rec[i][0].kind != "money", i))
    adj_all = deseason(np.vstack([r.raw for _, r in rec]), ax)
    kept: list[int] = []
    dropped: list[str] = []
    for i in order:
        dup = False
        for j in kept:
            a, b = adj_all[i], adj_all[j]
            ok_ = ~np.isnan(a) & ~np.isnan(b)
            if ok_.sum() >= MIN_PERIODS and np.std(a[ok_]) > 0 and np.std(b[ok_]) > 0 and abs(np.corrcoef(a[ok_], b[ok_])[0, 1]) > DUP_CORR:
                dup = True; dropped.append(f"{rec[i][0].name} (moves with {rec[j][0].name})"); break
        if not dup and len(kept) < MAX_MEASURES:
            kept.append(i)
    overall = {rec[i][0].name: rec[i][1] for i in kept}

    # ---- 2. slices for the kept measures ----
    all_series: list[SeriesRec] = [rec[i][1] for i in kept]
    top_money = next((m for m, _ in (rec[i] for i in kept) if m.col == p.money_col and m.kind == "money"), None)
    for i in kept:
        m, base = rec[i]
        v, mk0 = vec[m.name], mask_of(m) & ~np.isnan(vec[m.name])
        for col in p.slices:
            if col == m.col or (m.currency and col == p.currency_col) or (m.flag_col and m.flag_col.startswith(f"__rate__{col}")):
                continue
            codes, uniq = codes_for(col)
            sel0 = mk0 & (codes >= 0)
            cc = np.bincount(codes[sel0], minlength=len(uniq))
            keep = np.where(cc >= MIN_SLICE_ROWS)[0]
            if len(keep) < 2:
                continue
            keep = keep[np.argsort(-cc[keep])][:TOP_SLICE_VALUES]
            comp = -np.ones(len(uniq), dtype=np.int64); comp[keep] = np.arange(len(keep))
            c2 = comp[codes]
            sel = sel0 & (c2 >= 0)
            key = c2[sel] * T + idx[sel]
            sums = np.bincount(key, weights=v[sel], minlength=len(keep) * T).reshape(len(keep), T)
            cnts = np.bincount(key, minlength=len(keep) * T).reshape(len(keep), T)
            raws = _finish(sums, cnts, m.agg)
            for r, code in enumerate(keep):
                if np.isfinite(raws[r]).sum() >= MIN_PERIODS and np.nanstd(raws[r]) > 0:
                    all_series.append(SeriesRec(sid, m.name, base.family, m.kind, m.agg, col, str(uniq[code]), raws[r], cnts[r])); sid += 1
                if top_money is not None and m.name == top_money.name or m.agg == "count":
                    tot = np.where(base.raw > 0, base.raw, np.nan)       # share of the whole
                    with np.errstate(invalid="ignore", divide="ignore"):
                        share = sums[r] / np.where(np.bincount(idx[mk0], weights=v[mk0], minlength=T) > 0, np.bincount(idx[mk0], weights=v[mk0], minlength=T), np.nan)
                    if np.isfinite(share).sum() >= MIN_PERIODS and np.nanstd(share) > 0:
                        all_series.append(SeriesRec(sid, f"share of {m.name}", base.family + " share", "share", "share", col, str(uniq[code]), share, cnts[r])); sid += 1

    # ---- 3. adjust seasons, run the tests (a series identical to an earlier one is tested once) ----
    seen: set = set()
    unique_series = []
    for sr in all_series:
        key = (sr.measure, np.round(np.nan_to_num(sr.raw, nan=-9.87654321), 9).tobytes())
        if key in seen:
            continue
        seen.add(key); unique_series.append(sr)
    all_series = unique_series
    Y = deseason(np.vstack([s.raw for s in all_series]), ax)
    results: list[dict] = []
    for s, y_full in zip(all_series, Y):
        valid = ~np.isnan(y_full)
        pos = np.nonzero(valid)[0]
        y = y_full[valid]
        typical = float(np.median(s.cnt[valid])) if s.cnt is not None and valid.any() else 0.0
        if s.agg == "rate":                                   # rare events are lumpy: count the events, not the rows
            mean_rate = float(np.nanmean(s.raw))
            typical *= min(mean_rate, 1 - mean_rate)
        for r in run_tests(y, typical):
            r.update(sid=s.sid, pos=pos, y=y)
            results.append(r)
    if not results:
        return ScanResult(view_name or p.name, ax, [], overall, len(all_series), 0, dropped, time.time() - t0, list(ax.notes), ViewContext(p, ax), {}, {m.name: m for m in p.measures})
    pv = np.array([r["p"] for r in results]); qv = bh(pv)
    by_sid = {s.sid: s for s in all_series}
    leads = []
    for r, q in zip(results, qv):
        if q > EARLY_Q:
            continue
        s, pos, y = by_sid[r["sid"]], r["pos"], r["y"]
        n = len(y)
        if r["test"] == "shift":
            k = r["split"]; a, b = (int(pos[k]), int(pos[-1])); base_w = (int(pos[0]), int(pos[k - 1]))
            before, after = float(y[:k].mean()), float(y[k:].mean())
        elif r["test"] == "window":
            st, L = r["start"], r["length"]; a, b = int(pos[st]), int(pos[st + L - 1])
            inside = np.zeros(n, bool); inside[st:st + L] = True
            base_w = (int(pos[0]), int(pos[-1]))
            before, after = float(y[~inside].mean()), float(y[inside].mean())
        elif r["test"] == "trend":
            a, b = int(pos[0]), int(pos[-1]); base_w = (a, int(pos[n // 3]))
            third = max(3, n // 3)
            before, after = float(y[:third].mean()), float(y[-third:].mean())
        else:
            i = r["at"]; a = b = int(pos[i]); base_w = (int(pos[0]), int(pos[-1]))
            before, after = float(np.median(y)), float(y[i])
        delta = after - before
        leads.append({
            "sid": s.sid, "measure": s.measure, "family": s.family, "kind": s.kind, "agg": s.agg,
            "slice_col": s.slice_col, "slice_val": s.slice_val, "test": r["test"], "p": float(r["p"]), "q": float(q),
            "level": "confirmed" if (q <= CONFIRMED_Q and float(np.median(s.cnt[~np.isnan(s.raw)])) >= MIN_CONFIRM_ROWS) else "early",
            "sparse": bool(float(np.median(s.cnt[~np.isnan(s.raw)])) < MIN_CONFIRM_ROWS),
            "a": a, "b": b, "baseline": base_w, "before": before, "after": after, "delta": delta,
            "rel": (delta / abs(before)) if before else None, "periods": b - a + 1,
        })
    leads.sort(key=lambda d: d["q"])
    used = {l["sid"] for l in leads}
    return ScanResult(view_name or p.name, ax, leads, overall, len(all_series), len(results), dropped, time.time() - t0, list(ax.notes),
                      ViewContext(p, ax), {sid: by_sid[sid] for sid in used}, {m.name: m for m in p.measures})

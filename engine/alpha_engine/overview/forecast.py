"""A cautious 3-month forecast, with its own honesty check.

Plain statistics only (numpy), no AI and no paid service:
  1. Take complete months only.  Fewer than 6: no forecast.
  2. Seasonality: with 24+ months, a monthly pattern is measured from the data; with 12-23 it is measured and
     shrunk halfway to flat (one cycle is noisy); with fewer, none.
  3. Level and trend: damped Holt smoothing on the seasonally adjusted series (parameters picked on the data).
  4. Range: the model's own past one-step errors, widening with distance (about 80% of outcomes).
  5. Honesty check: hide the last 3 months, forecast them from what came before, compare with what really happened.
     If that test is wildly off the forecast is withheld; if there is too little history to test, it says so.
"""
from __future__ import annotations

import math
import re
from datetime import date

import numpy as np

HORIZON = 3
MIN_MONTHS = 6
TEST_MONTHS = 3
MIN_FOR_TEST = 9                 # complete months needed to hold out 3 and still fit on 6
WITHHOLD_ABOVE = 0.30            # backtest error above this: not worth showing
Z80 = 1.2816

_MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def _parse(label: str):
    m = re.match(r"([A-Za-z]{3}) (\d{4})$", label or "")
    return (int(m.group(2)), _MON[m.group(1).title()]) if m and m.group(1).title() in _MON else None


def _next(ym, k=1):
    y, m = ym
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def _label(ym):
    return f"{list(_MON)[ym[1] - 1]} {ym[0]}"


def _seasonal(y: np.ndarray, months: list[int]) -> dict[int, float]:
    n = len(y)
    if n < 12 or np.any(y <= 0):
        return {m: 1.0 for m in range(1, 13)}
    ratios: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for i in range(6, n - 6):                                   # ratio to a centred 12-month average
        base = (0.5 * y[i - 6] + y[i - 5:i + 6].sum() + 0.5 * y[i + 6]) / 12
        if base > 0:
            ratios[months[i]].append(y[i] / base)
    idx = {m: (float(np.mean(v)) if v else 1.0) for m, v in ratios.items()}
    mean = np.mean(list(idx.values())) or 1.0
    idx = {m: v / mean for m, v in idx.items()}
    if n < 24:                                                  # one cycle of evidence: trust it half as much
        idx = {m: 0.5 + 0.5 * v for m, v in idx.items()}
    return idx


def _holt(z: np.ndarray, a: float, b: float, phi: float):
    level, trend = z[0], (z[1] - z[0]) if len(z) > 1 else 0.0
    errs = []
    for v in z[1:]:
        pred = level + phi * trend
        errs.append(v - pred)
        new = a * v + (1 - a) * pred
        trend = b * (new - level) + (1 - b) * phi * trend
        level = new
    return level, trend, np.array(errs)


def _fit(y: np.ndarray, months: list[int]):
    seas = _seasonal(y, months)
    z = y / np.array([seas[m] for m in months])
    best = None
    for a in (0.2, 0.4, 0.6):
        for b in (0.05, 0.15, 0.3):
            level, trend, errs = _holt(z, a, b, 0.9)
            sse = float(np.sum(errs ** 2))
            if best is None or sse < best[0]:
                best = (sse, level, trend, errs)
    _, level, trend, errs = best
    return seas, level, trend, errs, z


def _predict(seas, level, trend, errs, z, last_ym, k=HORIZON, phi=0.9):
    sigma = float(np.std(errs)) if len(errs) > 2 else float(np.std(z)) * 0.3
    rel = sigma / max(abs(float(np.mean(z[-6:]))), 1e-9)
    mid, lo, hi = [], [], []
    damp = 0.0
    for h in range(1, k + 1):
        damp += phi ** h
        base = level + damp * trend
        ym = _next(last_ym, h)
        s = seas[ym[1]]
        spread = Z80 * sigma * math.sqrt(h) * s
        mid.append(max(base * s, 0.0)); lo.append(max(base * s - spread, 0.0)); hi.append(base * s + spread)
    return mid, lo, hi, rel


def make_forecast(x: list[str], values: list, data_end: date, data_start: date | None = None, nonneg: bool = True) -> dict:
    """x: month labels like 'Jan 2025'; values: one number per month. Returns a plain dict for the report."""
    pts = [(_parse(l), v) for l, v in zip(x, values)]
    if any(p is None or v is None for p, v in pts):
        return {"status": "none", "reason": "The months could not be read."}
    if pts and (data_end.year, data_end.month) == pts[-1][0] and data_end.day < _month_days(*pts[-1][0]):
        pts = pts[:-1]                                           # last month is not finished: leave it out
    if pts and data_start and (data_start.year, data_start.month) == pts[0][0] and data_start.day > 5:
        pts = pts[1:]                                            # first month started late
    n = len(pts)
    if n < MIN_MONTHS:
        return {"status": "none", "reason": f"Not enough history to forecast: {n} complete month{'s' if n != 1 else ''}, at least {MIN_MONTHS} are needed."}
    ym = [p for p, _ in pts]
    y = np.array([float(v) for _, v in pts])
    if nonneg and np.any(y < 0):
        return {"status": "none", "reason": "The series has negative months, so it is not forecast."}
    months = [m for _, m in ym]
    seas, level, trend, errs, z = _fit(y, months)
    mid, lo, hi, rel = _predict(seas, level, trend, errs, z, ym[-1])
    out = {"status": "ok", "grain": "month", "history_months": n, "seasonal": n >= 12,
           "x": [_label(_next(ym[-1], h)) for h in range(1, HORIZON + 1)], "mid": [round(float(v), 2) for v in mid], "low": [round(float(v), 2) for v in lo], "high": [round(float(v), 2) for v in hi],
           "last_actual": _label(ym[-1]),
           "method": "Trend and seasonal pattern from your own history" if n >= 12 else "Trend from your own history (too short to measure seasons)"}
    if n >= MIN_FOR_TEST:
        cut = n - TEST_MONTHS
        s2, l2, t2, e2, z2 = _fit(y[:cut], months[:cut])
        pm, _, _, _ = _predict(s2, l2, t2, e2, z2, ym[cut - 1])
        actual = y[cut:]
        err = float(np.mean(np.abs(np.array(pm) - actual) / np.maximum(np.abs(actual), 1e-9)))
        total_err = float(abs(sum(pm) - actual.sum()) / max(abs(actual.sum()), 1e-9))
        out["backtest"] = {"months": [_label(p) for p in ym[cut:]], "predicted": [round(float(v), 2) for v in pm], "actual": [round(float(v), 2) for v in actual],
                           "error": round(err, 4), "total_error": round(total_err, 4),
                           "grade": "good" if err < 0.08 else "fair" if err < 0.15 else "weak"}
        if err > WITHHOLD_ABOVE:
            return {"status": "none", "reason": f"Past months are too unpredictable to forecast: on your own history this method was off by about {err:.0%} per month.",
                    "backtest": out["backtest"]}
    else:
        out["backtest"] = None
        out["untested"] = f"Not enough history to test this forecast against your own past months (needs {MIN_FOR_TEST}, you have {n})."
    out["total"] = {"mid": round(float(sum(mid)), 2), "low": round(float(sum(lo)), 2), "high": round(float(sum(hi)), 2)}
    return out


def _month_days(y: int, m: int) -> int:
    return (date(y + (m == 12), m % 12 + 1, 1) - date(y, m, 1)).days

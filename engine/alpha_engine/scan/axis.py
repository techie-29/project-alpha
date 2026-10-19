"""Time axis for the scan: choose day / week / month, trim part-periods at the edges, remove normal seasons."""
from __future__ import annotations
from dataclasses import dataclass, field
import warnings
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d

MIN_PERIODS = 12


@dataclass
class Axis:
    step: str                       # 'day' | 'week' | 'month'
    freq: str
    starts: pd.DatetimeIndex        # start date of each kept period
    idx: np.ndarray                 # row -> period index (-1 = not on the axis)
    T: int
    per_year: int
    seasonal: bool
    slot: np.ndarray                # calendar month (0..11) of every period
    notes: list[str] = field(default_factory=list)

    def label(self, i: int) -> str:
        d = self.starts[i]
        return f"{d:%d %b %Y}" if self.step != "month" else f"{d:%b %Y}"

    def span_label(self, a: int, b: int) -> str:
        """Inclusive period range as readable dates."""
        return self.label(a) if a == b else f"{self.label(a)} to {self.label(b)}"


FREQ = {"day": ("D", 365), "week": ("W-SUN", 52), "month": ("M", 12)}


def choose_step(t: pd.Series, periodic: bool) -> str:
    d = t.dropna().dt.normalize().drop_duplicates().sort_values()
    span = (d.iloc[-1] - d.iloc[0]).days
    if periodic and len(d) > 2:
        gap = float(d.diff().dt.days.median())
        return "month" if gap >= 25 else ("week" if gap >= 6 else "day")
    if span <= 100:
        return "day"
    return "week" if span <= 6 * 365 else "month"


def build_axis(t: pd.Series, periodic: bool = False) -> Axis | None:
    t = t.copy()
    valid = t.notna()
    if valid.sum() < 30:
        return None
    step = choose_step(t, periodic)
    freq, per_year = FREQ[step]
    per = t[valid].dt.to_period(freq)
    ords = np.full(len(t), -(10 ** 9), dtype=np.int64)
    ords[valid.values] = per.array.asi8
    omin, omax = int(ords[valid.values].min()), int(ords[valid.values].max())
    notes: list[str] = []
    first_start = pd.Period(ordinal=omin, freq=freq).start_time
    last_end = pd.Period(ordinal=omax, freq=freq).end_time.normalize()
    tmin, tmax = t[valid].min().normalize(), t[valid].max().normalize()
    if step != "day":
        if tmin > first_start and omax - omin >= MIN_PERIODS + 1:
            omin += 1
            notes.append(f"Left out the first {step} (only part of it is in the data).")
        if tmax < last_end and omax - omin >= MIN_PERIODS + 1:
            omax -= 1
            notes.append(f"Left out the last {step} (only part of it is in the data).")
    T = omax - omin + 1
    if T < MIN_PERIODS:
        return None
    idx = ords - omin
    idx[(idx < 0) | (idx >= T)] = -1
    starts = pd.PeriodIndex.from_ordinals(np.arange(omin, omax + 1), freq=freq).start_time
    seasonal = T >= 3 * per_year
    if seasonal:
        notes.append("Normal seasonal pattern (typical value for each calendar month, using the median across years) was removed before looking for changes.")
    elif T >= 2 * per_year:
        notes.append("Two years of data: seasons are not removed (one-off events would be mistaken for seasons). Changes that repeat at the same time each year are marked as seasonal instead.")
    else:
        notes.append("Less than two years of data: normal seasons cannot be separated, so a seasonal swing could look like a change.")
    return Axis(step, freq, starts, idx, T, per_year, seasonal, starts.month.values - 1, notes)


def _roll(Y: np.ndarray, W: int) -> np.ndarray:
    M = ~np.isnan(Y)
    Y0 = np.where(M, Y, 0.0)
    num = uniform_filter1d(Y0, W, axis=1, mode="constant") * W
    cnt = uniform_filter1d(M.astype(float), W, axis=1, mode="constant") * W
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / cnt
    out[cnt < W / 2] = np.nan
    return out


def deseason(Y: np.ndarray, ax: Axis) -> np.ndarray:
    """Classical additive decomposition for many series at once (rows = series). Returns adjusted copy."""
    if not ax.seasonal:
        return Y.copy()
    W = ax.per_year if ax.per_year % 2 else ax.per_year + 1
    D = Y - _roll(Y, W)
    S = np.zeros((Y.shape[0], 12))
    for s in range(12):
        cols = ax.slot == s
        if cols.any():
            with np.errstate(all="ignore"):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    S[:, s] = np.nanmedian(D[:, cols], axis=1)
    S = np.nan_to_num(S)
    S -= S.mean(axis=1, keepdims=True)
    return Y - S[:, ax.slot]

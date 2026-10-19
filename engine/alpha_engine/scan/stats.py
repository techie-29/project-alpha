"""The statistical tests. Each test is judged against SHUFFLED versions of the same series (blocks of neighbouring
periods are shuffled together so slow drifts do not cause false alarms). Extreme results use an extreme-value fit
of the shuffles so tiny p-values stay meaningful. Nothing here knows what 'sales' or 'returns' are."""
from __future__ import annotations
import math
from functools import lru_cache
import numpy as np
from scipy.stats import norm, rankdata, skew, kurtosis, shapiro, t as t_dist

MIN_SIDE = 4                      # hand-set statistical minimum (documented limit)
WINDOW_LENGTHS = (2, 3, 4, 6, 8, 13, 26)
M1, M2 = 199, 1999                # shuffles: quick screen, then full run for promising results
EULER = 0.5772156649
OUTLIER_MIN_ROWS = 40             # one-period spikes are only judged where each period rests on enough rows to behave smoothly


def tail_p(obs: float, null: np.ndarray) -> float:
    m = len(null)
    k = int((null >= obs).sum())
    if k >= 10:
        return (k + 1) / (m + 1)
    beta = null.std() * math.sqrt(6) / math.pi
    if beta <= 0:
        return (k + 1) / (m + 1)
    loc = null.mean() - EULER * beta
    z = (obs - loc) / beta
    pg = -math.expm1(-math.exp(-z)) if z > -30 else 1.0
    return float(max(min(pg, (k + 1) / (m + 1)), 1e-300))


@lru_cache(maxsize=64)
def perms(n: int, b: int, m: int) -> np.ndarray:
    rng = np.random.default_rng(12345 + n * 7 + b)       # fixed seed: same file => same answer
    if b <= 1:
        return np.argsort(rng.random((m, n)), axis=1)
    nb = -(-n // b)
    out = np.empty((m, n), dtype=np.int64)
    base = [np.arange(i * b, min((i + 1) * b, n)) for i in range(nb)]
    for r in range(m):
        out[r] = np.concatenate([base[j] for j in rng.permutation(nb)])[:n]
    return out


def block_size(y: np.ndarray) -> int:
    """Shuffle blocks must be long enough to keep slow drifts together, or drifts look like changes."""
    n = len(y)
    if n < 24:
        return 1
    r = y - y.mean()
    den = float((r * r).sum())
    if den == 0:
        return 1
    ac = float((r[1:] * r[:-1]).sum() / den)
    if ac < 0.2:
        return 1
    return int(min(max(2, math.ceil(4 / max(1 - ac, 0.1))), max(2, n // 6)))


def _shift_stat(Y: np.ndarray, sd: float):
    """Y: (m, n). Largest standardised gap between the mean before and after any split. Returns stat, split."""
    m, n = Y.shape
    cs = np.cumsum(Y, axis=1)
    tot = cs[:, -1:]
    k = np.arange(MIN_SIDE, n - MIN_SIDE + 1)
    left = cs[:, k - 1] / k
    right = (tot - cs[:, k - 1]) / (n - k)
    t = np.abs(left - right) / (sd * np.sqrt(1 / k + 1 / (n - k)))
    j = t.argmax(axis=1)
    return t.max(axis=1), k[j]


def _window_stat(Y: np.ndarray, sd: float):
    m, n = Y.shape
    cs = np.concatenate([np.zeros((m, 1)), np.cumsum(Y, axis=1)], axis=1)
    tot = cs[:, -1:]
    best = np.zeros(m); bl = np.zeros(m, dtype=int); bs = np.zeros(m, dtype=int)
    for L in WINDOW_LENGTHS:
        if L > n // 3 or n - L < MIN_SIDE:
            continue
        ws = cs[:, L:] - cs[:, :-L]
        t = np.abs(ws / L - (tot - ws) / (n - L)) / (sd * math.sqrt(1 / L + 1 / (n - L)))
        mx, arg = t.max(axis=1), t.argmax(axis=1)
        upd = mx > best
        best = np.where(upd, mx, best); bl = np.where(upd, L, bl); bs = np.where(upd, arg, bs)
    return best, bl, bs


def _spearman(Ry: np.ndarray, rt: np.ndarray) -> np.ndarray:
    a = Ry - Ry.mean(axis=1, keepdims=True)
    b = rt - rt.mean()
    return (a @ b) / (np.sqrt((a * a).sum(axis=1)) * math.sqrt((b * b).sum()))


def _robust_z(Y: np.ndarray):
    med = np.median(Y, axis=-1, keepdims=True)
    mad = np.median(np.abs(Y - med), axis=-1, keepdims=True) * 1.4826
    sd = Y.std(axis=-1, keepdims=True)
    scale = np.where(mad > 0, mad, sd)
    scale = np.where(scale > 0, scale, np.nan)
    return np.abs(Y - med) / scale


def run_tests(y: np.ndarray, typical_rows: float = 1e9) -> list[dict]:
    """y: adjusted values with NaNs already removed. Returns up to four results (shift, window, trend, outlier)."""
    n = len(y)
    sd = float(y.std())
    if n < 12 or sd == 0 or not np.isfinite(sd):
        return []
    b = block_size(y)
    res: list[dict] = []

    def run(fn_obs, fn_null_all, name):
        obs = fn_obs()
        for m in (M1, M2):
            null = fn_null_all(m)
            p = tail_p(obs[0], null)
            if p > 0.1 or m == M2:
                break
        return p, obs

    # --- shift (level change that stays) ---
    stat0, split = _shift_stat(y[None, :], sd)
    p, _ = run(lambda: (float(stat0[0]),), lambda m: _shift_stat(y[perms(n, b, m)], sd)[0], "shift")
    res.append({"test": "shift", "p": p, "split": int(split[0])})
    # --- window (a stretch of 2..26 periods that differs from the rest) ---
    s0, l0, a0 = _window_stat(y[None, :], sd)
    if s0[0] > 0:
        p, _ = run(lambda: (float(s0[0]),), lambda m: _window_stat(y[perms(n, b, m)], sd)[0], "window")
        res.append({"test": "window", "p": p, "start": int(a0[0]), "length": int(l0[0])})
    # --- trend ---
    ry = rankdata(y)
    rt = np.arange(n, dtype=float)
    rho0 = float(_spearman(ry[None, :], rt)[0])

    def trend_null(m):
        return np.abs(_spearman(ry[perms(n, b, m)], rt))
    p, _ = run(lambda: (abs(rho0),), trend_null, "trend")
    if p <= 1 / (M2 + 1) + 1e-12:                   # beyond shuffle resolution: normal tail from the shuffle spread
        sdn = float(_spearman(ry[perms(n, b, M2)], rt).std())
        p = float(min(p, 2 * norm.sf(abs(rho0) / sdn))) if sdn > 0 else p
    res.append({"test": "trend", "p": max(p, 1e-300), "rho": rho0})
    # --- one-period outlier: judged only where the normal periods look bell-shaped (documented limit) ---
    if n >= 24 and typical_rows >= OUTLIER_MIN_ROWS and len(np.unique(y)) >= 0.6 * n:
        i = int(np.argmax(np.abs(y - np.median(y))))
        rest = np.delete(y, i)
        if abs(skew(rest)) < 0.5 and kurtosis(rest) < 1.0 and rest.std(ddof=1) > 0 and shapiro(rest[:5000]).pvalue > 0.1:
            z = abs(y[i] - rest.mean()) / (rest.std(ddof=1) * math.sqrt(1 + 1 / (n - 1)))
            p1 = float(2 * t_dist.sf(z, df=n - 2))
            p = min(1.0, -math.expm1(n * math.log1p(-min(p1, 1 - 1e-12))))
            res.append({"test": "outlier", "p": max(p, 1e-300), "at": i})
    return res


def bh(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values)."""
    m = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order] * m / (np.arange(m) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out

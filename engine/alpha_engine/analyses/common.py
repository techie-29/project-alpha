"""Shared pieces for the analysis toolbox: the insight record, shuffle tests, multiple-testing control, wording helpers."""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from ..scan.stats import bh

RNG_SEED = 12345
MIN_GROUP_ROWS = 30
TEST_SAMPLE = 60000


def fmt_value(v, fmt: str, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    if fmt == "pct":
        return f"{v * 100:.1f}%"
    if fmt == "rating":
        return f"{v:.2f}"
    if fmt == "days":
        return f"{v:.1f} days"
    a = abs(v)
    s = f"{v / 1e6:.2f}M" if a >= 1e6 else f"{v / 1e3:.1f}K" if a >= 1e4 else f"{v:,.0f}" if a >= 100 else f"{v:,.2f}"
    return f"{unit} {s}".strip() if fmt == "money" else s


def insight(kind: str, area: str, title: str, detail: str, **kw) -> dict:
    iid = hashlib.md5(f"{kind}|{title}".encode()).hexdigest()[:10]
    d = {"id": iid, "type": kind, "area": area, "title": title, "detail": detail, "strength": kw.pop("strength", "calculated"),
         "q": kw.pop("q", None), "p": kw.pop("p", None), "polarity": kw.pop("polarity", "neutral"), "impact": kw.pop("impact", None),
         "impact_unit": kw.pop("impact_unit", ""), "impact_share": kw.pop("impact_share", None), "actionable": kw.pop("actionable", False),
         "look_at": kw.pop("look_at", None), "numbers": kw.pop("numbers", {}), "chart": kw.pop("chart", None),
         "evidence": kw.pop("evidence", {}), "source": kw.pop("source", None), "tags": kw.pop("tags", []), "suggestion": kw.pop("suggestion", None)}
    d.update(kw)
    d["claim"] = {"calculated": "Calculated", "supported": "Supported by evidence", "early": "Possible (early sign)"}[d["strength"]]
    return d


def perm_group_test(num: np.ndarray, den: np.ndarray, codes: np.ndarray, k: int, B1: int = 199, B2: int = 1999, rng=None):
    """Shuffle test for 'is group g different from the rest' on a ratio of sums (means: den = 1).
    Returns per-group (diff, p). Group labels are shuffled; numerator/denominator stay with their row."""
    rng = rng or np.random.default_rng(RNG_SEED)
    n = len(codes)
    if n > TEST_SAMPLE:
        idx = rng.choice(n, TEST_SAMPLE, replace=False)
        num, den, codes = num[idx], den[idx], codes[idx]
    TN, TD = num.sum(), den.sum()

    def stat(c):
        gn = np.bincount(c, weights=num, minlength=k); gd = np.bincount(c, weights=den, minlength=k)
        with np.errstate(divide="ignore", invalid="ignore"):
            return gn / gd - (TN - gn) / (TD - gd)
    obs = stat(codes)
    absobs = np.abs(obs)

    def run(B):
        ge = np.zeros(k)
        for _ in range(B):
            ge += np.abs(stat(rng.permutation(codes))) >= absobs - 1e-12
        return ge
    ge = run(B1)
    p = (ge + 1) / (B1 + 1)
    if np.nanmin(p) < 0.03:
        ge2 = run(B2)
        p = np.where(p < 0.03, (ge2 + 1) / (B2 + 1), p)
    return obs, p


def perm_corr(x: np.ndarray, y: np.ndarray, B: int = 499, rng=None) -> tuple[float, float]:
    rng = rng or np.random.default_rng(RNG_SEED)
    if len(x) > 20000:
        i = rng.choice(len(x), 20000, replace=False); x, y = x[i], y[i]
    rx, ry = pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy()
    rx = (rx - rx.mean()) / (rx.std() or 1); ry = (ry - ry.mean()) / (ry.std() or 1)
    r = float(np.mean(rx * ry))
    ge = sum(abs(np.mean(rx * rng.permutation(ry))) >= abs(r) for _ in range(B))
    return r, (ge + 1) / (B + 1)


def apply_bh(items: list[dict], q_conf: float = 0.05, q_early: float = 0.10) -> list[dict]:
    """Benjamini-Hochberg across a family of tests; sets strength and drops what fails."""
    tested = [i for i in items if i.get("p") is not None]
    if not tested:
        return items
    q = bh(np.array([i["p"] for i in tested]))
    keep = [i for i in items if i.get("p") is None]
    for i, qq in zip(tested, q):
        i["q"] = float(qq)
        if qq <= q_conf:
            i["strength"] = "supported"
        elif qq <= q_early:
            i["strength"] = "early"
        else:
            continue
        i["claim"] = {"supported": "Supported by evidence", "early": "Possible (early sign)"}[i["strength"]]
        keep.append(i)
    return keep


def codes_of(s: pd.Series):
    c, u = pd.factorize(s.astype("string"), sort=False)
    return c, np.asarray(u, dtype=object)


def rows_sample(F, mask: pd.Series, cols: list[str], sort_col: str | None = None, n: int = 40) -> dict:
    d = F.df[mask]
    total = int(len(d))
    if sort_col and sort_col in d.columns:
        d = d.reindex(d[sort_col].abs().sort_values(ascending=False).index)
    cols = [c for c in dict.fromkeys(["_row", "_t"] + cols) if c in d.columns]
    sub = d[cols].head(n)
    out = []
    for r in sub.itertuples(index=False, name=None):
        out.append([None if (isinstance(v, float) and not np.isfinite(v)) or v is pd.NA or v is None or (not isinstance(v, str) and pd.isna(v)) else (v.date().isoformat() if isinstance(v, pd.Timestamp) else v) for v in r])
    return {"file": F.name, "total": total, "columns": ["source row" if c == "_row" else "date" if c == "_t" else c for c in cols], "rows": out}

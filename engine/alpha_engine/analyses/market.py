"""Prices and other levels over time (share prices, NAVs, balances): how much they moved, the deepest fall from a peak,
how jumpy they are and whether that changed, the biggest single days, and which series move together.
Prices are levels: they are never added up, and every number here is a plain calculation on the rows."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import insight, fmt_value, RNG_SEED


def _cap(t: str) -> str:
    return t[:1].upper() + t[1:]


def _series(F, col: str) -> dict[str, pd.Series]:
    """One clean daily series per symbol (or a single one)."""
    d = F.df[F.df["_t"].notna() & F.df[col].notna()]
    tick = (F.groups.get("ticker") or [None])[0]
    out = {}
    if tick and tick in d.columns:
        for k, g in d.groupby(tick):
            s = g.groupby("_t")[col].last().sort_index()
            if len(s) >= 30:
                out[str(k)] = s
    else:
        s = d.groupby("_t")[col].last().sort_index()
        if len(s) >= 30:
            out[""] = s
    return out


def _per_year(s: pd.Series) -> float:
    step = float(np.median(np.diff(s.index.values).astype("timedelta64[D]").astype(float))) if len(s) > 2 else 1.0
    return 252.0 if step <= 1.5 else (52.0 if step <= 8 else 12.0)


def run(F, currency: str | None) -> list[dict]:
    if F is None or not F.has_time:
        return []
    col = "price_level" if "price_level" in F.df.columns else ("level_value" if "level_value" in F.df.columns else None)
    if col is None:
        return []
    ser = _series(F, col)
    if not ser:
        return []
    word = "price" if col == "price_level" else "level"
    unit = currency or ""
    out = []
    for name, s in ser.items():
        who = f"{name} " if name else ""
        tag = [name] if name else []
        first, last = float(s.iloc[0]), float(s.iloc[-1])
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        total = last / first - 1 if first > 0 else None
        # 1. overall move
        if total is not None:
            cagr = (last / first) ** (1 / yrs) - 1 if yrs >= 1.5 and first > 0 and last > 0 else None
            out.append(insight("price_move", "market", _cap(f"{who}{word} {'rose' if total > 0 else 'fell'} {abs(total):.0%} over the period"),
                               f"From {fmt_value(first, 'money', unit)} on {s.index[0]:%d %b %Y} to {fmt_value(last, 'money', unit)} on {s.index[-1]:%d %b %Y}"
                               + (f", about {cagr:+.1%} a year." if cagr is not None else "."),
                               polarity="good" if total > 0 else "bad", numbers={"start": first, "end": last, "change": total, "per_year": cagr},
                               chart=_line(s, f"{who}{word} over time", unit), source=F.name, tags=["market", "move"] + tag))
        # 2. deepest fall from a peak (max drawdown)
        peak = s.cummax()
        dd = s / peak - 1
        trough = dd.idxmin()
        mdd = float(dd.min())
        if mdd <= -0.1:
            pk = s[:trough].idxmax()
            rec = s[trough:][s[trough:] >= s[pk]]
            back = f"It got back to that peak on {rec.index[0]:%d %b %Y}." if len(rec) else f"It has not yet returned to that peak ({fmt_value(last, 'money', unit)} now, {last / s[pk] - 1:+.0%})."
            out.append(insight("drawdown", "market", _cap(f"{who}deepest fall: {mdd:.0%} from the {pk:%b %Y} peak"),
                               f"From {fmt_value(float(s[pk]), 'money', unit)} on {pk:%d %b %Y} down to {fmt_value(float(s[trough]), 'money', unit)} on {trough:%d %b %Y}. {back}",
                               polarity="bad", numbers={"drawdown": mdd, "peak_date": str(pk.date()), "trough_date": str(trough.date())},
                               chart={**_line(s, f"{who}{word} and its deepest fall", unit), "focus_range": [pk.strftime("%d %b %Y"), trough.strftime("%d %b %Y")]},
                               source=F.name, tags=["market", "drawdown"] + tag, suggestion="Decide in advance how large a fall you are prepared to hold through, and check it against this one."))
        # 3. jumpiness, and whether the last 3 months were calmer or wilder than the year before
        r = s.pct_change().dropna()
        k = _per_year(s)
        if len(r) >= 60:
            vol = float(r.std() * np.sqrt(k))
            recent_n = int(k / 4)
            rec, before = r.iloc[-recent_n:], r.iloc[-recent_n - int(k):-recent_n]
            if len(before) >= recent_n and len(rec) >= 10:
                ratio = float(rec.std() / before.std()) if before.std() > 0 else np.nan
                p = _var_ratio_p(rec.values, before.values)
                if np.isfinite(ratio) and (ratio >= 1.5 or ratio <= 0.67) and p < 0.01:
                    out.append(insight("volatility", "market", _cap(f"{who}{word} has been {'much jumpier' if ratio > 1 else 'much calmer'} in the last 3 months ({ratio:.1f}x the swings of the year before)"),
                                       f"Typical swing per {'day' if k == 252 else 'period'}: {rec.std():.1%} recently against {before.std():.1%} before. Over the whole period it moves about {vol:.0%} a year (annualised).",
                                       strength="supported", p=p, polarity="bad" if ratio > 1 else "neutral", numbers={"ratio": ratio, "annual_vol": vol},
                                       source=F.name, tags=["market", "volatility"] + tag))
            # 4. biggest single moves
            big = r.abs().sort_values(ascending=False).head(3)
            if len(big) and big.iloc[0] >= 4 * r.std():
                rows = [{"group": f"{i:%d %b %Y}", "value": float(r[i])} for i in big.index]
                out.append(insight("big_days", "market", _cap(f"{who}biggest single {'day' if k == 252 else 'period'}: {r[big.index[0]]:+.1%} on {big.index[0]:%d %b %Y}"),
                                   "The three largest moves were " + ", ".join(f"{r[i]:+.1%} on {i:%d %b %Y}" for i in big.index) + f"; a typical move is {r.std():.1%}.",
                                   polarity="neutral", numbers={"moves": [float(r[i]) for i in big.index]},
                                   chart={"type": "bar", "title": "Largest single moves", "fmt": "pct", "rows": rows, "keep_order": True},
                                   source=F.name, tags=["market", "big_days"] + tag, suggestion="Check what happened on those dates (results, news, splits)."))
    # 5. which series move together (returns, not price levels, so a shared upward drift does not count)
    if len(ser) >= 2:
        R = pd.DataFrame({k: v.pct_change() for k, v in ser.items()}).dropna(how="all")
        C = R.corr(min_periods=60)
        pairs = [(a, b, float(C.loc[a, b])) for i, a in enumerate(C.columns) for b in C.columns[i + 1:] if np.isfinite(C.loc[a, b])]
        if pairs:
            pairs.sort(key=lambda x: -x[2])
            hi, lo = pairs[0], pairs[-1]
            out.append(insight("comovement", "market", f"{hi[0]} and {hi[1]} move together most closely (correlation {hi[2]:.2f})",
                               f"Correlation of day-to-day changes. Least related: {lo[0]} and {lo[1]} ({lo[2]:.2f}). Series that move together give less protection when held together.",
                               polarity="neutral", numbers={"pairs": [{"a": a, "b": b, "r": r} for a, b, r in pairs[:10]]},
                               chart={"type": "table", "title": "How closely each pair moves together", "columns": ["Correlation"], "fmts": {},
                                      "rows": [{"key": f"{a} & {b}", "Correlation": round(r, 2)} for a, b, r in pairs[:15]]},
                               source=F.name, tags=["market", "correlation"]))
        moves = {k: float(v.iloc[-1] / v.iloc[0] - 1) for k, v in ser.items() if v.iloc[0] > 0}
        if len(moves) >= 2:
            best, worst = max(moves, key=moves.get), min(moves, key=moves.get)
            out.append(insight("price_rank", "market", f"{best} gained the most ({moves[best]:+.0%}); {worst} the least ({moves[worst]:+.0%})",
                               "Change from each series' first to last date in the file.", polarity="neutral",
                               chart={"type": "bar", "title": "Change over the period", "fmt": "pct", "rows": [{"group": k, "value": v} for k, v in sorted(moves.items(), key=lambda kv: -kv[1])]},
                               numbers={"moves": moves}, source=F.name, tags=["market", "ranking"]))
    return out


def _line(s: pd.Series, title: str, unit: str) -> dict:
    if len(s) > 400:                                   # weekly points keep the chart light
        s = s.resample("W").last().dropna()
    return {"type": "line", "title": title, "fmt": "money", "unit": unit, "x": [f"{i:%d %b %Y}" for i in s.index], "values": [float(f"{v:.5g}") for v in s.values]}


def _var_ratio_p(a: np.ndarray, b: np.ndarray, B: int = 999) -> float:
    """Shuffle test: is the spread of a different from the spread of b?"""
    rng = np.random.default_rng(RNG_SEED)
    obs = abs(np.log(a.std() / b.std()))
    x = np.concatenate([a, b])
    n = len(a)
    ge = 0
    for _ in range(B):
        rng.shuffle(x)
        ge += abs(np.log(x[:n].std() / x[n:].std())) >= obs
    return (ge + 1) / (B + 1)

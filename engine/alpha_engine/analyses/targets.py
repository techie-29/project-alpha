"""Per-row measures that analyses compare across groups, over time and against each other."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from ..metrics.frame import Frame


@dataclass
class Target:
    id: str
    label: str
    num: str            # numerator column
    den: str | None     # denominator column (None = mean of num)
    scope: str          # ok | all
    fmt: str            # money | pct | days | rating | number
    polarity: int
    money: bool = False
    kind: str = "mean"  # mean | ratio | rate

    def arrays(self, F: Frame, currency: str | None):
        d = F.df
        m = d["_ok"].astype(bool) if self.scope == "ok" else pd.Series(True, index=d.index)
        if self.money and "_cur" in d.columns and currency:
            m &= d["_cur"] == currency
        num = pd.to_numeric(d[self.num], errors="coerce").astype(float)
        den = pd.to_numeric(d[self.den], errors="coerce").astype(float) if self.den else pd.Series(1.0, index=d.index)
        m &= num.notna() & den.notna()
        if self.den:
            m &= den > 0
        return m.to_numpy(), num.to_numpy(), den.to_numpy()


def targets(F: Frame) -> list[Target]:
    d, T = F.df, []
    has = F.has
    if F.role == "transactions" and has("revenue"):
        T.append(Target("aov" if has("order_id") else "avg_sale", "Average order value" if has("order_id") else "Average sale", "revenue", None, "ok", "money", +1, True))
    if has("profit", "revenue"):
        T.append(Target("margin", "Profit margin", "profit", "revenue", "ok", "pct", +1, True, "ratio"))
    if has("discount", "gross_revenue"):
        T.append(Target("discount_rate", "Discount rate", "discount", "gross_revenue", "ok", "pct", -1, True, "ratio"))
    kept: list[np.ndarray] = []
    flags = sorted(F.status_flags, key=lambda x: (0 if x[0] in F.groups.get("status", [])[:1] else 1, x[1] == "yes"))
    for col, val, fc in flags:
        if fc not in d.columns:
            continue
        v = d[fc].fillna(False).astype(bool).to_numpy()
        if any(_agree(v, w) for w in kept):
            continue                                 # 'cancelled' in order status and in delivery status are the same thing
        kept.append(v)
        lab = f"{val} rate ({col.replace('_', ' ')})" if val != "yes" else f"Share with a {col.replace('_', ' ')}"
        T.append(Target(f"rate:{fc}", lab[0].upper() + lab[1:], fc, None, "all", "pct", -1, False, "rate"))
    if has("_on_time"):
        T.append(Target("on_time", "On-time rate", "_on_time", None, "all", "pct", +1, False, "rate"))
    if has("_late"):
        T.append(Target("late", "Average delay vs promise", "_late", None, "all", "days", -1))
    elif has("duration"):
        T.append(Target("duration", "Average time taken", "duration", None, "all", "days", -1))
    if has("rating"):
        T.append(Target("rating", "Average rating", "rating", None, "all", "rating", +1))
    return T


def _agree(a: np.ndarray, b: np.ndarray) -> bool:
    if a.sum() == 0 or b.sum() == 0:
        return False
    j = (a & b).sum() / (a | b).sum()
    return j >= 0.75


OUTCOME_GROUPS = {"status", "sentiment", "reason"}       # results of what happened: shown, but never used to explain other results


def group_columns(F: Frame, max_levels: int = 60) -> list[str]:
    skip = {"name_label", "personal", "free_text", "currency"} | OUTCOME_GROUPS
    out = []
    for g, cols in F.groups.items():
        if g in skip:
            continue
        for c in cols:
            if c in F.df.columns:
                nu = F.df[c].nunique(dropna=True)
                if 2 <= nu <= max_levels:
                    out.append(c)
    return list(dict.fromkeys(out))

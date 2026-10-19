"""Files with no usable dates cannot say what CHANGED. They can still say which groups STAND OUT.
Every result is labelled a snapshot, never a trend."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import f_oneway
from ..understand.prepare import Prepared, MIN_SLICE_ROWS
from ..understand.roles import clean_numeric
from .stats import bh


def snapshot(p: Prepared, max_findings: int = 12) -> dict | None:
    df, cands = p.df, []
    meas = [c for c, i in p.roles.items() if i["role"] == "measure"]
    cats = [c for c in p.slices if c in df.columns]
    for m in meas:
        v = pd.to_numeric(df[m], errors="coerce") if pd.api.types.is_numeric_dtype(df[m]) else clean_numeric(df[m])
        if v is None or v.notna().sum() < 3 * MIN_SLICE_ROWS or v.std() == 0:
            continue
        for c in cats:
            if c == m:
                continue
            g = pd.DataFrame({"v": v, "g": df[c].astype(str).where(df[c].notna())}).dropna()
            sizes = g.groupby("g").size()
            ok = sizes[sizes >= MIN_SLICE_ROWS].index
            if len(ok) < 2:
                continue
            g = g[g.g.isin(ok)]
            groups = [x.v.values for _, x in g.groupby("g")]
            try:
                F, pval = f_oneway(*groups)
            except Exception:
                continue
            if not np.isfinite(pval):
                continue
            overall = g.v.mean()
            gm = g.groupby("g").v.agg(["mean", "count"])
            gm["gap"] = (gm["mean"] - overall) / (g.v.std() or 1)
            top = gm.reindex(gm.gap.abs().sort_values(ascending=False).index).head(3)
            cands.append({"measure": m, "by": c, "p": float(pval), "overall": float(overall),
                          "groups": [{"value": str(i), "mean": float(r["mean"]), "rows": int(r["count"]), "gap_in_sd": float(r["gap"])} for i, r in top.iterrows()]})
    if not cands:
        return None
    q = bh(np.array([c["p"] for c in cands]))
    out = []
    for c, qq in zip(cands, q):
        if qq <= 0.05:
            g = c["groups"][0]
            c.update(q=float(qq), title=f"{c['measure'].replace('_', ' ').capitalize()} differs by {c['by'].replace('_', ' ')}: {g['value']} is {'higher' if g['gap_in_sd'] > 0 else 'lower'} than the rest",
                     detail=f"Average {g['mean']:,.2f} for {g['value']} ({g['rows']:,} rows) versus {c['overall']:,.2f} overall.", claim="Snapshot (not a trend)")
            out.append(c)
    out.sort(key=lambda c: c["q"])
    return {"view": p.name, "kind": "snapshot", "findings": out[:max_findings], "tested": len(cands),
            "note": "This file has no usable dates, so it can show which groups stand out but not what changed over time."}

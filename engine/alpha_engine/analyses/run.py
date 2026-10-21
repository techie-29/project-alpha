"""Run the whole analysis toolbox over the business's frames and return every insight found, plus what was checked."""
from __future__ import annotations
import time
import numpy as np
from . import groups, concentration, trends, relations, customers, stock, outliers, explore, changes


def run_all(pick: dict, views_by_name: dict, progress=lambda s, p: None) -> tuple[list[dict], dict]:
    S, L, K = pick.get("sales"), pick.get("lines"), pick.get("stock")
    cur = S.currency if S else (L.currency if L else None)
    avg_order = None
    if S is not None and "revenue" in S.df.columns:
        d = S.df[S.df["_ok"].astype(bool)]
        if "_cur" in d.columns and cur:
            d = d[d["_cur"] == cur]
        avg_order = float(d["revenue"].mean()) if len(d) else None
    timing, out, checked = {}, [], {}

    def step(name, fn, pct):
        progress(f"Looking for {name}", pct)
        t = time.time()
        try:
            res = fn()
        except Exception as e:                         # one analysis failing never stops the report
            checked.setdefault("failed", []).append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
            res = []
        timing[name] = round(time.time() - t, 1)
        if isinstance(res, tuple):
            res, extra = res
            checked[name] = extra
        out.extend(res)

    step("group differences", lambda: groups.run(S, cur, avg_order) if S is not None else [], 35)
    if L is not None:
        step("product differences", lambda: groups.run(L, cur, None, skip_cols=set(S.df.columns) if S is not None else None), 42)
    step("concentration", lambda: concentration.run([S, L], cur), 46)
    step("trends and seasons", lambda: trends.run(S, cur), 50)
    step("relationships", lambda: relations.run(S, cur), 55)
    step("customer behaviour", lambda: customers.run(S, cur), 60)
    step("stock health", lambda: stock.run(K, [L, S], cur), 63)
    step("unusual values", lambda: outliers.run([L, S], cur), 66)
    step("hidden combinations", lambda: explore.run(S, cur), 72)
    sv = views_by_name.get(S.name) if S is not None else None
    step("changes over time", lambda: changes.run(sv, S), 85)
    checked["timing"] = timing
    return out, checked

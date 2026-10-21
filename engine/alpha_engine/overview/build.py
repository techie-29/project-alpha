"""'Here is your business': what the files contain, headline numbers with comparisons, and charts for every area
the data supports. Built only from frames + the metric catalogue, so it adapts to any business."""
from __future__ import annotations
import numpy as np
import pandas as pd
from ..metrics.frame import Frame
from ..metrics.catalogue import available, generic_metrics, value, series, by_group, BY_ID, Metric
from ..model.concepts import CONCEPTS

ROLE_TEXT = {"transactions": "Activity log", "lines": "Line items", "master": "Master list", "snapshot": "Snapshot over time", "periodic": "Period totals",
             "reference": "Reference table", "summary": "Summary (not analysed)", "other": "Other"}
GROUP_ORDER = ["channel", "location", "product_group", "segment", "site_id", "payment_method", "delivery_method", "campaign", "status", "gender", "sentiment",
               "reason", "employee_id", "supplier_id", "name_label", "yes_no", "group"]
MAX_DAY_POINTS = 2200


def _span(F: Frame):
    if not F.has_time:
        return None
    t = F.df["_t"].dropna()
    return (t.min(), t.max()) if len(t) else None


def describe_files(frames: dict[str, Frame], file_infos: dict) -> list[dict]:
    out = []
    for name, F in frames.items():
        sp = _span(F)
        ent = F.entity
        n = len(F.df)
        if F.role == "master" and ent:
            what = f"List of {n:,} {ent}s"
        elif F.role == "lines":
            k = F.df["order_id"].nunique() if "order_id" in F.df else None
            what = f"{n:,} line items" + (f" for {k:,} orders" if k else "")
        elif F.role == "snapshot":
            k = F.df["product_id"].nunique() if "product_id" in F.df else None
            what = f"Counts for {k:,} items over {F.df['_t'].dt.normalize().nunique():,} dates" if k and sp else f"{n:,} snapshot rows"
        elif F.role == "transactions":
            what = f"{n:,} records"
        else:
            what = f"{n:,} rows"
        out.append({"name": name, "role": F.role, "role_text": ROLE_TEXT.get(F.role, F.role), "entity": ent, "rows": n, "what": what,
                    "from": sp[0].date().isoformat() if sp else None, "to": sp[1].date().isoformat() if sp else None,
                    "currency": F.currency, "currencies": F.currencies, "reason": file_infos.get(name, {}).get("reason", "")})
    for name, fi in file_infos.items():
        if name not in frames:
            out.append({"name": name, "role": fi.get("role", "summary"), "role_text": ROLE_TEXT.get(fi.get("role", "summary"), ""), "entity": None, "rows": None,
                        "what": "Summary of other files, used only for cross-checking", "from": None, "to": None, "currency": None, "currencies": [], "reason": fi.get("reason", "")})
    return out


def pick_frames(frames: dict[str, Frame], links: list) -> dict[str, Frame | None]:
    used = [l for l in links if getattr(l, "use", False)]
    tx = [F for F in frames.values() if F.role in ("transactions", "periodic")]
    parents_of_lines = {l.parent for l in used if frames.get(l.child) and frames[l.child].role == "lines"}
    def rank(F):
        return (F.has("revenue"), F.name in parents_of_lines, F.has("_t") if F.has_time else False, len(F.df))
    sales = max(tx, key=rank) if tx else None
    lines = [F for F in frames.values() if F.role == "lines"]
    lines_f = max(lines, key=lambda F: (F.has("revenue") or F.has("quantity"), len(F.df))) if lines else None
    if sales is None and lines_f is not None and lines_f.has_time:
        sales = lines_f
    masters = {F.entity: F for F in frames.values() if F.role == "master" and F.entity}
    stock = [F for F in frames.values() if F.has("stock_level")]
    return {"sales": sales, "lines": lines_f, "customers": masters.get("customer"), "products": masters.get("product"),
            "stock": max(stock, key=lambda F: (F.role == "snapshot", len(F.df))) if stock else None}


def _complete_month_end(F: Frame):
    t = F.df["_t"].dropna()
    last = t.max()
    month_end = (last + pd.offsets.MonthEnd(0)).normalize()
    return last.normalize() >= month_end - pd.Timedelta(days=1), last


def tile(F: Frame, m: Metric, cur: str | None) -> dict | None:
    v = value(F, m, cur)
    if v is None:
        return None
    t = {"metric": m.id, "label": m.label, "value": v, "fmt": m.fmt, "unit": cur if m.money else (F.duration_unit if m.fmt == "days" else ""), "polarity": m.polarity, "how": m.how,
         "source": F.name, "area": m.area}
    if F.has_time and m.spec[0] not in ("latest_count_if",):
        labels, vals = series(F, m, "month", cur)
        if len(vals) >= 3:
            complete, last = _complete_month_end(F)
            idx = len(vals) - 1 if complete else len(vals) - 2
            t["spark"] = vals[max(0, idx - 23): idx + 1]
            t["spark_labels"] = labels[max(0, idx - 23): idx + 1]
            if idx >= 1 and vals[idx] is not None and vals[idx - 1]:
                t["last_period"] = {"label": labels[idx], "value": vals[idx], "previous": vals[idx - 1], "previous_label": labels[idx - 1],
                                    "change": _chg(vals[idx], vals[idx - 1], m.fmt)}
            if idx >= 12 and vals[idx - 12]:
                t["vs_last_year"] = {"label": labels[idx - 12], "value": vals[idx - 12], "change": _chg(vals[idx], vals[idx - 12], m.fmt)}
            if not complete:
                t["note"] = f"{labels[-1]} is not complete yet (data ends {last.date().isoformat()}), so comparisons use {labels[idx]}."
            if idx >= 23 and m.spec[0] in ("sum", "count", "nunique") and m.id not in ("customers", "products_sold"):
                a = sum(x or 0 for x in vals[idx - 11: idx + 1]); b = sum(x or 0 for x in vals[idx - 23: idx - 11])
                if b:
                    t["last_12_months"] = {"value": a, "previous": b, "change": (a - b) / abs(b)}
    return t


def _chg(a, b, fmt):
    if a is None or b in (None, 0):
        return None
    return (a - b) if fmt in ("pct",) else (a - b) / abs(b)


def _r(v):
    """Round chart values to 5 significant digits to keep the report small."""
    if v is None:
        return None
    return float(f"{v:.5g}")


DAY_GRAIN_METRICS = {"revenue", "orders", "transactions", "customers", "units", "stock_value", "stock_units"}


def time_chart(F: Frame, m: Metric, cur: str | None, title: str | None = None, cid: str | None = None) -> dict | None:
    if not F.has_time:
        return None
    grains = {}
    span_days = (F.df["_t"].max() - F.df["_t"].min()).days if F.df["_t"].notna().any() else 0
    for g in ("day", "week", "month", "quarter", "year"):
        if g == "day" and (span_days > MAX_DAY_POINTS or (m.id not in DAY_GRAIN_METRICS and span_days > 120)):
            continue
        if g == "year" and span_days < 400:
            continue
        if g == "quarter" and span_days < 270:
            continue
        x, y = series(F, m, g, cur)
        if len(x) >= 2:
            grains[g] = {"x": x, "series": [{"name": m.label, "values": [_r(v) for v in y]}]}
    if not grains:
        return None
    default = "month" if "month" in grains and span_days > 120 else ("week" if "week" in grains and span_days > 30 else next(iter(grains)))
    return {"id": cid or f"{F.name}:{m.id}:time", "type": "line", "title": title or f"{m.label} over time", "metric": m.id, "fmt": m.fmt,
            "unit": cur if m.money else (F.duration_unit if m.fmt == "days" else ""), "grains": grains, "default_grain": default, "source": F.name, "how": m.how}


def bar_chart(F: Frame, m: Metric, col: str, cur: str | None, top: int = 12) -> dict | None:
    rows = by_group(F, m, col, cur, top)
    if len(rows) < 2:
        return None
    return {"id": f"{F.name}:{m.id}:by:{col}", "type": "bar", "title": f"{m.label} by {col.replace('_', ' ')}", "metric": m.id, "fmt": m.fmt,
            "unit": cur if m.money else (F.duration_unit if m.fmt == "days" else ""), "group_col": col, "rows": rows, "source": F.name, "how": m.how}


def stacked_share(F: Frame, m: Metric, col: str, cur: str | None, top: int = 6) -> dict | None:
    if not F.has_time or m.spec[0] != "sum":
        return None
    d = F.df[F.df["_ok"].astype(bool) & F.df[col].notna() & F.df["_t"].notna()]
    if m.money and "_cur" in d.columns and cur:
        d = d[d["_cur"] == cur]
    if not len(d) or d[col].nunique() < 2:
        return None
    topv = d.groupby(col)[m.spec[1]].sum().sort_values(ascending=False).index[:top]
    g = d.assign(_g=d[col].where(d[col].isin(topv), "Other"), _p=d["_t"].dt.to_period("M").dt.start_time).groupby(["_p", "_g"])[m.spec[1]].sum().unstack(fill_value=0)
    g = g.div(g.sum(axis=1).replace(0, np.nan), axis=0)
    return {"id": f"{F.name}:{m.id}:share:{col}", "type": "stacked", "title": f"Share of {m.label.lower()} by {col.replace('_', ' ')}, per month", "fmt": "pct",
            "x": [x.strftime("%b %Y") for x in g.index], "series": [{"name": str(c), "values": [None if not np.isfinite(v) else float(v) for v in g[c].values]} for c in g.columns],
            "source": F.name}


def profile_chart(F: Frame, m: Metric, cur: str | None, kind: str) -> dict | None:
    if not F.has_time or m.spec[0] != "sum":
        return None
    d = F.df[F.df["_ok"].astype(bool) & F.df["_t"].notna()]
    if m.money and "_cur" in d.columns and cur:
        d = d[d["_cur"] == cur]
    if kind == "weekday":
        days = pd.Series(1, index=pd.date_range(d["_t"].min().normalize(), d["_t"].max().normalize())).groupby(lambda x: x.weekday()).sum()
        if len(days) < 7:
            return None
        v = d.groupby(d["_t"].dt.weekday)[m.spec[1]].sum().reindex(range(7)).fillna(0) / days.reindex(range(7)).values
        return {"id": f"{F.name}:{m.id}:weekday", "type": "bar", "title": f"Average {m.label.lower()} per day, by weekday", "fmt": m.fmt, "unit": cur if m.money else "",
                "rows": [{"group": n, "value": float(x)} for n, x in zip(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], v.values)], "keep_order": True, "source": F.name}
    months = d["_t"].dt.to_period("M").nunique()
    if months < 13:
        return None
    per = d.groupby([d["_t"].dt.year, d["_t"].dt.month])[m.spec[1]].sum()
    avg = per.groupby(level=1).mean().reindex(range(1, 13))
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return {"id": f"{F.name}:{m.id}:month_of_year", "type": "bar", "title": f"Average {m.label.lower()} by calendar month", "fmt": m.fmt, "unit": cur if m.money else "",
            "rows": [{"group": n, "value": None if not np.isfinite(x) else float(x)} for n, x in zip(names, avg.values)], "keep_order": True, "source": F.name}


def histogram(F: Frame, col: str, title: str, fmt: str = "number", unit: str = "", bins: int = 20) -> dict | None:
    v = pd.to_numeric(F.df.loc[F.df["_ok"].astype(bool), col], errors="coerce").dropna() if col in F.df else pd.Series(dtype=float)
    if len(v) < 30 or v.nunique() < 3:
        return None
    lo, hi = v.quantile(0.005), v.quantile(0.995)
    v = v.clip(lo, hi)
    if v.nunique() <= bins:
        vc = v.value_counts().sort_index()
        rows = [{"group": f"{k:g}", "value": int(c)} for k, c in vc.items()]
    else:
        cnt, edges = np.histogram(v, bins=bins)
        rows = [{"group": f"{edges[i]:,.0f}–{edges[i + 1]:,.0f}" if hi - lo > 50 else f"{edges[i]:.1f}–{edges[i + 1]:.1f}", "value": int(c)} for i, c in enumerate(cnt)]
    return {"id": f"{F.name}:{col}:hist", "type": "histogram", "title": title, "fmt": "count", "unit": unit, "rows": rows, "keep_order": True, "source": F.name,
            "stats": {"median": float(v.median()), "mean": float(v.mean()), "p10": float(v.quantile(0.1)), "p90": float(v.quantile(0.9))}}


def ranking(F: Frame, key: str, metrics: list[Metric], cur: str | None, label_col: str | None, title: str, top: int = 15) -> dict | None:
    if key not in F.df.columns or not metrics:
        return None
    d = F.df[F.df["_ok"].astype(bool) & F.df[key].notna()]
    main = metrics[0]
    if main.money and "_cur" in d.columns and cur:
        d = d[d["_cur"] == cur]
    if not len(d):
        return None
    from ..metrics.catalogue import _agg, _latest
    cols = {}
    for m in metrics:
        try:
            cols[m.label] = _latest(d, m.spec, key, None) if m.spec[0] in ("latest_level", "latest_count_if") else _agg(d, m.spec, key)
        except Exception:
            continue
    if main.label not in cols:
        return None
    tab = pd.DataFrame(cols).sort_values(main.label, ascending=False)
    total = float(tab[main.label].sum()) if main.spec[0] in ("sum", "count", "nunique") else None
    names = d.groupby(key)[label_col].first() if label_col and label_col in d.columns else None
    rows = []
    for k, r in tab.head(top).iterrows():
        row = {"key": str(k), "name": (str(names.get(k)) if names is not None and pd.notna(names.get(k)) else None)}
        for c in tab.columns:
            row[c] = None if not np.isfinite(r[c]) else float(r[c])
        if total:
            row["share"] = float(r[main.label]) / total
        rows.append(row)
    bottom = [{"key": str(k), "name": (str(names.get(k)) if names is not None and pd.notna(names.get(k)) else None), main.label: float(r[main.label])}
              for k, r in tab.tail(5).iterrows()] if len(tab) > top else []
    return {"id": f"{F.name}:{key}:rank", "type": "table", "title": title, "columns": list(tab.columns), "fmts": {m.label: m.fmt for m in metrics},
            "unit": cur if main.money else "", "rows": rows, "bottom": bottom, "count": int(len(tab)), "source": F.name}


def customers_section(F: Frame, cur: str | None) -> list[dict]:
    """New vs returning customers per month, repeat rate."""
    if not (F.has_time and F.has("customer_id")):
        return []
    d = F.df[F.df["_ok"].astype(bool) & F.df["_t"].notna() & F.df["customer_id"].notna()]
    if not len(d):
        return []
    out = []
    first = d.groupby("customer_id")["_t"].min().dt.to_period("M")
    d = d.assign(_m=d["_t"].dt.to_period("M"))
    act = d.groupby("_m")["customer_id"].nunique()
    new = first.value_counts().reindex(act.index).fillna(0)
    out.append({"id": f"{F.name}:customers:new_returning", "type": "stacked_count", "title": "Customers per month: new and returning", "fmt": "count",
                "x": [p.start_time.strftime("%b %Y") for p in act.index],
                "series": [{"name": "New", "values": [float(x) for x in new.values]}, {"name": "Returning", "values": [float(x) for x in (act - new).values]}], "source": F.name})
    per = d.groupby("customer_id")["order_id"].nunique() if "order_id" in d else d.groupby("customer_id").size()
    rep = float((per >= 2).mean())
    dist = per.clip(upper=10).value_counts().sort_index()
    out.append({"id": f"{F.name}:customers:orders_each", "type": "histogram", "title": "How many times each customer bought", "fmt": "count",
                "rows": [{"group": (f"{int(k)}" if k < 10 else "10+"), "value": int(v)} for k, v in dist.items()], "keep_order": True, "source": F.name,
                "stats": {"repeat_rate": rep, "customers": int(len(per)), "median": float(per.median())}})
    return out


def build_overview(frames: dict[str, Frame], file_infos: dict, links: list) -> dict:
    pick = pick_frames(frames, links)
    S, L, C, P, K = pick["sales"], pick["lines"], pick["customers"], pick["products"], pick["stock"]
    cur = next((F.currency for F in (S, L, K, P, C) if F is not None and F.currency), None)
    tiles, sections = [], {}

    def add(area, chart):
        if chart:
            sections.setdefault(area, []).append(chart)

    used_metric_ids = set()
    # ---- headline tiles ----
    cands = []
    for F in [x for x in (S, K) if x] + ([C] if C and not (S and S.has("customer_id")) else []) + ([P] if P else []):
        for m in available(F):
            cands.append((m.headline, F, m))
    if L and S and not S.has("quantity") and L.has("quantity"):
        cands += [(m.headline, L, m) for m in available(L) if m.id in ("units", "products_sold", "avg_selling_price")]
    seen, per_area = set(), {}
    cap = {"sales": 6, "customers": 3, "operations": 3, "stock": 4, "service": 2, "costs": 2, "products": 2, "general": 2, "people": 1}
    for h, F, m in sorted(cands, key=lambda x: -x[0]):
        if h <= 0 or m.id in seen or per_area.get(m.area, 0) >= cap.get(m.area, 2):
            continue
        t = tile(F, m, cur if m.money else None)
        if t:
            tiles.append(t); seen.add(m.id); per_area[m.area] = per_area.get(m.area, 0) + 1
        if len(tiles) >= 16:
            break
    # ---- sales ----
    if S:
        ms = {m.id: m for m in available(S)}
        main = ms.get("revenue") or ms.get("orders") or ms.get("transactions") or next(iter(ms.values()), None)
        if main:
            for mid in ("revenue", "orders", "transactions", "aov", "profit", "margin", "units", "discount_rate"):
                if mid in ms:
                    add("sales", time_chart(S, ms[mid], cur if ms[mid].money else None))
            groups = [c for g in GROUP_ORDER for c in S.groups.get(g, []) if g not in ("name_label",) and 2 <= S.df[c].nunique() <= 60]
            for c in groups[:8]:
                add("sales", bar_chart(S, main, c, cur if main.money else None))
            for c in groups[:2]:
                add("sales", stacked_share(S, main, c, cur if main.money else None))
            add("sales", profile_chart(S, main, cur if main.money else None, "month"))
            add("sales", profile_chart(S, main, cur if main.money else None, "weekday"))
            if "revenue" in S.df:
                add("sales", histogram(S, "revenue", "Size of each sale", "money", cur or ""))
            if "_cur" in S.df.columns and len(S.currencies) > 1 and "revenue" in ms:
                rows = by_group(S, Metric("rev_all", "Revenue", "sales", (), ("sum", "revenue"), "money"), "_cur", None, 20)
                sections.setdefault("sales", []).append({"id": f"{S.name}:currencies", "type": "bar", "title": "Revenue by currency (each in its own currency)", "fmt": "money",
                                                         "unit": "", "rows": rows, "source": S.name, "note": "Amounts in different currencies are not added together; this only shows their size."})
            if "profit" in ms and S.groups.get("product_group"):
                add("costs", bar_chart(S, ms["margin"], S.groups["product_group"][0], None)) if "margin" in ms else None
            used_metric_ids |= set(ms)
        # operations & service
        for mid in ("avg_duration", "on_time_rate", "avg_late"):
            if mid in ms:
                add("operations", time_chart(S, ms[mid], None))
        for c in [c for g in ("delivery_method", "site_id", "location", "channel") for c in S.groups.get(g, [])][:3]:
            for mid in ("on_time_rate", "avg_duration"):
                if mid in ms:
                    add("operations", bar_chart(S, ms[mid], c, None)); break
        for mid, m in ms.items():
            if mid.startswith("rate:"):
                add("operations", time_chart(S, m, None))
        for c in S.groups.get("status", [])[:3]:
            add("operations", bar_chart(S, Metric("rows_all", "Rows", "operations", (), ("count",), "count"), c, None))
        if "duration" in S.df:
            add("operations", histogram(S, "duration", f"How long it took ({S.duration_unit})", "days"))
        if "avg_rating" in ms:
            add("service", time_chart(S, ms["avg_rating"], None))
            add("service", histogram(S, "rating", "Ratings given"))
            for c in [c for g in ("product_group", "channel", "delivery_method", "site_id") for c in S.groups.get(g, [])][:3]:
                add("service", bar_chart(S, ms["avg_rating"], c, None))
        for c in S.groups.get("sentiment", [])[:1] + S.groups.get("reason", [])[:2]:
            add("service", bar_chart(S, Metric("rows_all", "Rows", "service", (), ("count",), "count"), c, None))
        # customers
        if "customers" in ms:
            add("customers", time_chart(S, ms["customers"], None, "Active customers over time"))
            for ch in customers_section(S, cur):
                add("customers", ch)
            rk = ranking(S, "customer_id", [m for m in (ms.get("revenue"), ms.get("orders")) if m], cur, None, "Top customers")
            add("customers", rk)
            for c in [c for g in ("segment", "location", "gender") for c in S.groups.get(g, [])][:3]:
                if "revenue_per_customer" in ms:
                    add("customers", bar_chart(S, ms["revenue_per_customer"], c, cur))
        # generic numbers
        for m in generic_metrics(S, set())[:8]:
            add("other", time_chart(S, m, cur if m.money else None))
    # ---- products (prefer line items) ----
    PF = L if (L and L.has("product_id")) else (S if S and S.has("product_id") else None)
    if PF:
        pm = {m.id: m for m in available(PF)}
        main = pm.get("revenue") or pm.get("units")
        label_col = (PF.groups.get("name_label") or [None])[0]
        if main:
            rk = ranking(PF, "product_id", [m for m in (pm.get("revenue"), pm.get("units"), pm.get("profit"), pm.get("orders")) if m], cur, label_col, "Top products")
            add("products", rk)
            for c in PF.groups.get("product_group", [])[:3]:
                add("products", bar_chart(PF, main, c, cur if main.money else None))
                if "margin" in pm:
                    add("products", bar_chart(PF, pm["margin"], c, None))
            if "units" in pm:
                add("products", time_chart(PF, pm["units"], None))
    if P:
        for c in P.groups.get("product_group", [])[:2]:
            add("products", bar_chart(P, Metric("rows_all", "Products", "products", (), ("count",), "count", roles=("master",)), c, None))
        if "unit_price" in P.df:
            add("products", histogram(P, "unit_price", "Product prices", "money", cur or ""))
    # ---- customers master ----
    if C:
        for c in [c for g in ("segment", "location", "gender") for c in C.groups.get(g, [])][:4]:
            add("customers", bar_chart(C, Metric("rows_all", "Customers", "customers", (), ("count",), "count", roles=("master",)), c, None))
        if "age" in C.df:
            add("customers", histogram(C, "age", "Customer ages"))
    # ---- stock ----
    if K:
        km = {m.id: m for m in available(K)}
        main = km.get("stock_value") or km.get("stock_units")
        if main:
            if K.has_time:
                add("stock", time_chart(K, main, cur if main.money else None))
            for c in K.groups.get("product_group", [])[:2] + K.groups.get("site_id", [])[:1]:
                add("stock", bar_chart(K, main, c, cur if main.money else None))
            label_col = (K.groups.get("name_label") or [None])[0]
            add("stock", ranking(K, "product_id", [main] + [m for m in (km.get("stock_units"),) if m and m is not main], cur, label_col, "Largest stock holdings"))
    return {"files": describe_files(frames, file_infos), "currency": cur,
            "currencies": (S.currencies if S else []), "tiles": tiles,
            "sections": [{"area": a, "title": _area_title(a), "charts": sections[a]} for a in
                         ("sales", "products", "customers", "operations", "service", "stock", "costs", "other") if sections.get(a)],
            "sources": {k: (v.name if v else None) for k, v in pick.items()}}


def _area_title(a):
    return {"sales": "Sales", "products": "Products", "customers": "Customers", "operations": "Operations", "service": "Service and satisfaction",
            "stock": "Stock", "costs": "Costs and margin", "other": "Other numbers"}[a]

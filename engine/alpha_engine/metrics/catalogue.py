"""The metric catalogue: calculation recipes written once in code. A metric switches on only when the frame has
the concepts it needs. Every metric can be evaluated overall, per period (day/week/month/quarter/year) and per group."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .frame import Frame, MONEY
from ..model.concepts import CONCEPTS

FLOW_ROLES = ("transactions", "lines", "periodic")


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    area: str
    needs: tuple
    spec: tuple
    fmt: str                       # money | count | pct | days | rating | number | ratio
    polarity: int = 0
    roles: tuple = FLOW_ROLES
    how: str = ""                  # plain description of the calculation
    money: bool = False
    headline: int = 0              # >0: candidate for the top tiles (higher = more important)


def M(*a, **k):
    return Metric(*a, **k)


S = lambda c: ("sum", c)
N = lambda c: ("nunique", c)
A = lambda c: ("mean", c)
R = lambda a, b: ("ratio", a, b)
CNT = ("count",)

CATALOGUE: list[Metric] = [
    # ---------------- sales ----------------
    M("revenue", "Revenue", "sales", ("revenue",), S("revenue"), "money", +1, how="sum of revenue on rows that count", money=True, headline=100),
    M("orders", "Orders", "sales", ("order_id",), N("order_id"), "count", +1, how="number of distinct orders", headline=90),
    M("transactions", "Transactions", "sales", (), CNT, "count", +1, roles=("transactions",), how="number of rows that count", headline=40),
    M("aov", "Average order value", "sales", ("revenue", "order_id"), R(S("revenue"), N("order_id")), "money", +1, how="revenue / orders", money=True, headline=80),
    M("avg_sale", "Average sale", "sales", ("revenue",), A("revenue"), "money", +1, roles=("transactions",), how="average revenue per row", money=True, headline=30),
    M("units", "Units sold", "sales", ("quantity",), S("quantity"), "count", +1, how="sum of units", headline=60),
    M("units_per_order", "Units per order", "sales", ("quantity", "order_id"), R(S("quantity"), N("order_id")), "number", +1, how="units / orders"),
    M("avg_selling_price", "Average selling price", "sales", ("revenue", "quantity"), R(S("revenue"), S("quantity")), "money", 0, how="revenue / units", money=True),
    M("gross_sales", "Gross sales", "sales", ("gross_revenue",), S("gross_revenue"), "money", +1, how="sum of gross sales", money=True),
    M("discounts", "Discounts given", "sales", ("discount",), S("discount"), "money", -1, how="sum of discounts", money=True, headline=20),
    M("discount_rate", "Discount rate", "sales", ("discount", "gross_revenue"), R(S("discount"), S("gross_revenue")), "pct", -1, how="discounts / gross sales", headline=35),
    M("tax", "Tax collected", "sales", ("tax",), S("tax"), "money", 0, how="sum of tax", money=True),
    M("profit", "Profit", "sales", ("profit",), S("profit"), "money", +1, how="sum of profit", money=True, headline=95),
    M("margin", "Profit margin", "sales", ("profit", "revenue"), R(S("profit"), S("revenue")), "pct", +1, how="profit / revenue", headline=85),
    M("cost", "Cost of goods", "costs", ("cost",), S("cost"), "money", -1, how="sum of cost", money=True, headline=25),
    M("expenses", "Other expenses", "costs", ("expense",), S("expense"), "money", -1, how="sum of the main expense column", money=True, headline=15),
    M("cost_ratio", "Cost as share of revenue", "costs", ("cost", "revenue"), R(S("cost"), S("revenue")), "pct", -1, how="cost / revenue"),
    # ---------------- customers ----------------
    M("customers", "Customers", "customers", ("customer_id",), N("customer_id"), "count", +1, how="number of distinct customers", headline=88),
    M("revenue_per_customer", "Revenue per customer", "customers", ("revenue", "customer_id"), R(S("revenue"), N("customer_id")), "money", +1, how="revenue / customers", money=True, headline=45),
    M("orders_per_customer", "Orders per customer", "customers", ("order_id", "customer_id"), R(N("order_id"), N("customer_id")), "number", +1, how="orders / customers", headline=40),
    M("avg_customer_age", "Average customer age", "customers", ("age",), A("age"), "number", 0, roles=FLOW_ROLES + ("master",), how="average age"),
    # ---------------- products ----------------
    M("products_sold", "Products sold", "products", ("product_id",), N("product_id"), "count", +1, how="number of distinct products with sales", headline=50),
    M("avg_unit_price", "Average unit price", "products", ("unit_price",), A("unit_price"), "money", 0, roles=FLOW_ROLES + ("master",), how="average of unit price", money=True),
    M("product_count", "Products in catalogue", "products", ("product_id",), N("product_id"), "count", 0, roles=("master",), how="number of products listed", headline=30),
    # ---------------- stock ----------------
    M("stock_units", "Stock on hand", "stock", ("stock_level",), ("latest_level", "stock_level"), "count", 0, roles=("snapshot", "master"), how="units on hand, latest count per item", headline=70),
    M("stock_value", "Stock value (at cost)", "stock", ("_stock_value",), ("latest_level", "_stock_value"), "money", 0, roles=("snapshot", "master"), how="units on hand x unit cost, latest count per item", money=True, headline=75),
    M("stock_value_retail", "Stock value (at price)", "stock", ("_stock_value_retail",), ("latest_level", "_stock_value_retail"), "money", 0, roles=("snapshot", "master"), how="units on hand x unit price", money=True, headline=60),
    M("out_of_stock", "Items out of stock", "stock", ("stock_level",), ("latest_count_if", "stock_level", "zero"), "count", -1, roles=("snapshot", "master"), how="items whose latest count is 0", headline=55),
    M("below_reorder", "Items at or below reorder level", "stock", ("stock_level", "reorder_level"), ("latest_count_if", "stock_level", "reorder"), "count", -1, roles=("snapshot", "master"), how="items whose latest count is at or below their reorder level", headline=50),
    M("stock_items", "Items tracked", "stock", ("product_id", "stock_level"), N("product_id"), "count", 0, roles=("snapshot", "master"), how="number of distinct items with a stock count"),
    # ---------------- operations / service ----------------
    M("avg_duration", "Average time taken", "operations", ("duration",), A("duration"), "days", -1, roles=FLOW_ROLES, how="average of the time-taken column", headline=50),
    M("avg_promised", "Average promised time", "operations", ("promised_duration",), A("promised_duration"), "days", 0, how="average promised time"),
    M("avg_late", "Average delay vs promise", "operations", ("_late",), A("_late"), "days", -1, how="average of actual minus promised time", headline=45),
    M("on_time_rate", "On-time rate", "operations", ("_on_time",), ("flag", "_on_time"), "pct", +1, how="share of rows where actual time <= promised time", headline=58),
    M("avg_rating", "Average rating", "service", ("rating",), A("rating"), "rating", +1, roles=FLOW_ROLES + ("master",), how="average rating", headline=65),
    M("avg_margin_pct", "Average margin % (per row)", "sales", ("margin_pct",), A("margin_pct"), "number", +1, how="average of the margin column"),
    M("points", "Points", "customers", ("points",), S("points"), "count", 0, how="sum of points"),
    M("activity", "Activity", "general", ("activity_count",), S("activity_count"), "count", +1, how="sum of the activity column", headline=30),
    M("employees", "People involved", "people", ("employee_id",), N("employee_id"), "count", 0, how="distinct employees / agents", headline=20),
    M("sites", "Sites", "operations", ("site_id",), N("site_id"), "count", 0, how="distinct stores / sites", headline=15),
]
BY_ID = {m.id: m for m in CATALOGUE}

GRAINS = {"day": "D", "week": "W-MON", "month": "MS", "quarter": "QS", "year": "YS"}


def available(F: Frame) -> list[Metric]:
    out = []
    for m in CATALOGUE:
        if F.role not in m.roles:
            continue
        if not all(F.has(n) for n in m.needs):
            continue
        if m.spec[0] in ("latest_level", "latest_count_if") and F.role == "snapshot" and not F.has_time:
            continue
        out.append(m)
    if F.role in FLOW_ROLES:
        for col, val, fc in F.status_flags:
            if fc in F.df.columns and F.df[fc].notna().any():
                label = f"{val} rate ({col.replace('_', ' ')})" if val != "yes" else f"Share of rows with a {col.replace('_', ' ')}"
                out.append(Metric(f"rate:{fc}", label[0].upper() + label[1:], "operations", (fc,), ("flag", fc), "pct", -1,
                                  how=f"share of all rows where {col} is {val}" if val != "yes" else f"share of all rows where {col} is filled in", headline=57))
    ids = {m.id for m in out}
    if "orders" in ids:
        out = [m for m in out if m.id not in ("transactions", "avg_sale")]
    if "product_count" in ids and F.role == "master":
        out = [m for m in out if m.id != "products_sold"]
    return out


def generic_metrics(F: Frame, used_cols: set) -> list[Metric]:
    """Every remaining number column still gets a basic metric (sum for flows, average otherwise)."""
    out = []
    for c, cid in F.extra_numbers:
        if c in used_cols:
            continue
        con = CONCEPTS[cid]
        agg = "sum" if con.agg == "sum" and F.role in FLOW_ROLES else "mean"
        label = c.replace("_", " ").strip().capitalize()
        out.append(Metric(f"col:{c}", label if agg == "sum" else f"Average {label.lower()}", con.area if con.area != "general" else "other",
                          (c,), (agg, c), "money" if con.money and agg == "sum" else "number", con.polarity, roles=(F.role,),
                          how=f"{'sum' if agg == 'sum' else 'average'} of {c}", money=con.money))
    return out


# ---------------- evaluation ----------------
def _mask(F: Frame, m: Metric, currency: str | None) -> pd.Series:
    d = F.df
    all_rows = m.spec[0] == "flag" or m.id in ("rows_all",)
    mk = pd.Series(True, index=d.index) if all_rows else d["_ok"].astype(bool)
    if m.money and "_cur" in d.columns and currency:
        mk &= d["_cur"] == currency
    return mk


def _agg(d: pd.DataFrame, spec: tuple, keys):
    op = spec[0]
    g = d.groupby(keys, observed=True, sort=True) if keys is not None else None
    if op == "sum":
        return g[spec[1]].sum(min_count=1) if g is not None else d[spec[1]].sum(min_count=1)
    if op == "mean":
        return g[spec[1]].mean() if g is not None else d[spec[1]].mean()
    if op == "nunique":
        return g[spec[1]].nunique() if g is not None else d[spec[1]].nunique()
    if op == "count":
        return g.size() if g is not None else float(len(d))
    if op == "flag":
        v = d[spec[1]].astype(float)
        return v.groupby([d[k] for k in (keys if isinstance(keys, list) else [keys])], observed=True).mean() if keys is not None else v.mean()
    if op == "ratio":
        a, b = _agg(d, spec[1], keys), _agg(d, spec[2], keys)
        if keys is None:
            return a / b if b else np.nan
        return (a / b.replace(0, np.nan))
    raise ValueError(op)


def _latest(d: pd.DataFrame, spec: tuple, keys, item: str | None):
    """Stock levels: take the latest count per item (within each group/period), then add across items. Never add over time."""
    col = spec[1]
    if "_t" in d.columns and d["_t"].notna().any():
        d = d.sort_values("_t")
    it = item if item and item in d.columns else None
    gk = ([keys] if isinstance(keys, str) else list(keys or []))
    if it:
        last = d.groupby(gk + [it], observed=True, sort=False).tail(1) if gk else d.groupby(it, sort=False).tail(1)
    else:
        last = d[d["_t"] == d["_t"].max()] if "_t" in d.columns else d
        if gk and "_t" in d.columns:
            last = d[d.groupby(gk, observed=True)["_t"].transform("max") == d["_t"]]
    if spec[0] == "latest_level":
        return last.groupby(gk, observed=True)[col].sum(min_count=1) if gk else last[col].sum(min_count=1)
    rule = spec[2]
    hit = (last[col] <= 0) if rule == "zero" else (last[col] <= last["reorder_level"])
    return hit.groupby([last[k] for k in gk], observed=True).sum() if gk else float(hit.sum())


def value(F: Frame, m: Metric, currency: str | None = None, mask: pd.Series | None = None) -> float | None:
    d = F.df[_mask(F, m, currency) & (mask if mask is not None else True)]
    if not len(d):
        return None
    if m.spec[0] in ("latest_level", "latest_count_if"):
        v = _latest(d, m.spec, None, "product_id" if "product_id" in d.columns else None)
    else:
        v = _agg(d, m.spec, None)
    v = float(v) if v is not None and np.isfinite(v) else None
    return v


def series(F: Frame, m: Metric, grain: str, currency: str | None = None) -> tuple[list[str], list]:
    if not F.has_time:
        return [], []
    d = F.df[_mask(F, m, currency) & F.df["_t"].notna()].copy()
    if not len(d):
        return [], []
    d["_p"] = d["_t"].dt.to_period({"day": "D", "week": "W-SUN", "month": "M", "quarter": "Q", "year": "Y"}[grain]).dt.start_time
    if m.spec[0] in ("latest_level", "latest_count_if"):
        s = _latest(d, m.spec, "_p", "product_id" if "product_id" in d.columns else None)
    else:
        s = _agg(d, m.spec, "_p")
    full = pd.period_range(d["_p"].min(), d["_p"].max(), freq={"day": "D", "week": "W-SUN", "month": "M", "quarter": "Q", "year": "Y"}[grain]).start_time
    s = s.reindex(full)
    if m.spec[0] in ("sum", "count", "nunique") and m.spec[0] != "ratio":
        s = s.fillna(0)
    fmt = {"day": "%d %b %Y", "week": "%d %b %Y", "month": "%b %Y", "quarter": "Q%q %Y", "year": "%Y"}[grain]
    labels = [f"Q{(x.month - 1) // 3 + 1} {x.year}" if grain == "quarter" else x.strftime(fmt) for x in s.index]
    return labels, [None if not np.isfinite(v) else float(v) for v in s.values.astype(float)]


def by_group(F: Frame, m: Metric, col: str, currency: str | None = None, top: int = 12) -> list[dict]:
    d = F.df[_mask(F, m, currency) & F.df[col].notna()]
    if not len(d):
        return []
    if m.spec[0] in ("latest_level", "latest_count_if"):
        s = _latest(d, m.spec, col, "product_id" if "product_id" in d.columns and col != "product_id" else None)
    else:
        s = _agg(d, m.spec, col)
    rows = d.groupby(col, observed=True).size()
    s = s.dropna()
    total = None
    if m.spec[0] in ("sum", "count", "nunique", "latest_level"):
        total = float(s.sum()) if len(s) else None
    order = s.sort_values(ascending=False)
    out = []
    for k, v in order.head(top).items():
        out.append({"group": str(k), "value": float(v), "rows": int(rows.get(k, 0)), "share": (float(v) / total) if total else None})
    rest = order.iloc[top:]
    if len(rest) and total and m.spec[0] in ("sum", "count", "latest_level"):
        out.append({"group": f"Other ({len(rest)})", "value": float(rest.sum()), "rows": int(rows.reindex(rest.index).sum()), "share": float(rest.sum()) / total, "other": True})
    return out

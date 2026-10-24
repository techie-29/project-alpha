"""The metric catalogue: calculation recipes written once in code. A metric switches on only when the frame has
the concepts it needs. Every metric can be evaluated overall, per period (day/week/month/quarter/year) and per group."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .frame import Frame, MONEY
from ..model.concepts import CONCEPTS

import re as _re
LOSS_WORDS = _re.compile(r"damage|expired|wastage|waste|write ?off|loss|lost|theft|shrink|scrap|spoil|broken", _re.I)
FLOW_ROLES = ("transactions", "lines", "periodic", "snapshot")      # a daily stock panel also carries flows (units sold per day)


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
    M("units_received", "Units received", "stock", ("units_received",), S("units_received"), "count", 0, how="sum of units received / bought", headline=35),
    M("units_ordered", "Units ordered", "stock", ("units_ordered",), S("units_ordered"), "count", 0, how="sum of units ordered from suppliers", headline=20),
    M("fill_rate", "Received vs ordered", "stock", ("units_received", "units_ordered"), R(S("units_received"), S("units_ordered")), "pct", +1, how="units received / units ordered", headline=40),
    M("purchase_value", "Purchases (at cost)", "costs", ("_purchase_value",), S("_purchase_value"), "money", 0, how="units bought x unit cost", money=True, headline=45),
    M("units_lost", "Units damaged / lost", "stock", ("_units_lost",), S("_units_lost"), "count", -1, how="units in damaged / expired / lost movements", headline=42),
    M("loss_rate", "Loss rate", "stock", ("_units_lost", "_units_out_all"), R(S("_units_lost"), S("_units_out_all")), "pct", -1, how="units lost / (units sold + units lost)", headline=48),
    M("avg_cover", "Days of stock left", "stock", ("_cover_days",), A("_cover_days"), "days", 0, how="stock on hand / average units sold per day, averaged over items"),
    M("stock_items", "Items tracked", "stock", ("product_id", "stock_level"), N("product_id"), "count", 0, roles=("snapshot", "master"), how="number of distinct items with a stock count"),
    M("forecast", "Forecast / plan", "sales", ("forecast",), S("forecast"), "number", 0, how="sum of the forecast column", headline=12),
    M("forecast_error", "Forecast error", "sales", ("_fc_abs_err", "quantity"), R(S("_fc_abs_err"), S("quantity")), "pct", -1, how="sum of |forecast - actual| / actual units", headline=38),
    M("forecast_bias", "Forecast vs actual", "sales", ("forecast", "quantity"), R(S("forecast"), S("quantity")), "pct", 0, how="forecast / actual units (100% = spot on; above = over-forecast)"),
    M("price_vs_competitor", "Price vs competitors", "products", ("_price_gap",), A("_price_gap"), "pct", 0, how="average of (our price / competitor price - 1)", headline=33),
    M("avg_discount_pct", "Average discount %", "sales", ("discount_pct",), A("discount_pct"), "pct", -1, how="average discount percentage per row", headline=22),
    # ---------------- market / levels (latest value, never added up) ----------------
    M("price_last", "Latest price", "market", ("price_level",), ("last", "price_level"), "money", 0, roles=FLOW_ROLES, how="price on the latest date", money=True, headline=92),
    M("price_avg", "Average price", "market", ("price_level",), A("price_level"), "money", 0, roles=FLOW_ROLES, how="average price", money=True),
    M("price_high", "Highest price", "market", ("price_level",), ("max", "price_level"), "money", 0, roles=FLOW_ROLES, how="highest price in the period", money=True, headline=55),
    M("price_low", "Lowest price", "market", ("price_level",), ("min", "price_level"), "money", 0, roles=FLOW_ROLES, how="lowest price in the period", money=True, headline=54),
    M("daily_return_sd", "Daily price swing", "market", ("_ret",), ("std", "_ret"), "pct", -1, roles=FLOW_ROLES, how="standard deviation of day-to-day % change (volatility)", headline=50),
    M("volume", "Volume traded", "market", ("trade_volume",), S("trade_volume"), "count", 0, roles=FLOW_ROLES, how="sum of traded volume", headline=60),
    M("level_last", "Latest level", "general", ("level_value",), ("last", "level_value"), "number", 0, roles=FLOW_ROLES, how="value on the latest date", headline=45),
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
    if "_units_lost" in F.df.columns or str(F.canon.get("quantity", "")).endswith("is a sale / issue"):
        out = [m for m in out if m.id not in ("orders", "aov", "units_per_order", "orders_per_customer", "avg_sale")]   # a stock ledger: rows are movements, not orders
        import dataclasses as _dc
        out = [_dc.replace(m, label="Stock movements", how="number of movement rows (in, out, sales, damage...)") if m.id == "transactions" else m for m in out]
    dc = str(F.canon.get("duration", ""))
    if dc.startswith("days from"):
        import dataclasses
        lab = dc.replace("days from", "Days from")
        out = [dataclasses.replace(m, label=f"Average {lab[0].lower() + lab[1:]}", how=f"average of {dc}") if m.id == "avg_duration" else
               (dataclasses.replace(m, label="Average days late (vs due date)") if m.id == "avg_late" else m) for m in out]
    if "price_level" in F.df.columns or "level_value" in F.df.columns:
        out = [m for m in out if m.id not in ("transactions", "orders", "avg_sale", "aov")]    # rows of a price table are dates, not sales
    if any(m.id == "loss_rate" for m in out):        # 'Damaged rate' from the movement column says the same as the loss rate
        out = [m for m in out if not (m.id.startswith("rate:") and "__rate__" in m.id and LOSS_WORDS.search(m.id))]
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
        agg = "sum" if con.agg == "sum" and F.role in FLOW_ROLES else ("last" if con.agg == "level" and F.has_time else "mean")
        label = c.replace("_", " ").strip()
        label = label[0].upper() + label[1:] if label else c
        shown = label if agg == "sum" else (f"Latest {label}" if agg == "last" else f"Average {label.lower()}")
        out.append(Metric(f"col:{c}", shown, con.area if con.area != "general" else "other",
                          (c,), (agg, c), "money" if con.money and agg in ("sum", "last") else "number", con.polarity, roles=(F.role,),
                          how=f"{dict(sum='sum', last='value on the latest date of', mean='average')[agg]} {c}", money=con.money))
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
    if op in ("max", "min", "std"):
        return getattr(g[spec[1]], op)() if g is not None else getattr(d[spec[1]], op)()
    if op == "last":
        dd = d.sort_values("_t") if "_t" in d.columns else d
        dd = dd[dd[spec[1]].notna()]
        if g is not None:
            return dd.groupby(keys, observed=True, sort=True)[spec[1]].last()
        return dd[spec[1]].iloc[-1] if len(dd) else np.nan
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
    its = [x for x in ([item] if isinstance(item, str) else list(item or [])) if x in d.columns]
    gk = ([keys] if isinstance(keys, str) else list(keys or []))
    its = [x for x in its if x not in gk]
    if its:
        last = d.groupby(gk + its, observed=True, sort=False).tail(1)
    else:
        last = d[d["_t"] == d["_t"].max()] if "_t" in d.columns else d
        if gk and "_t" in d.columns:
            last = d[d.groupby(gk, observed=True)["_t"].transform("max") == d["_t"]]
    if spec[0] == "latest_level":
        return last.groupby(gk, observed=True)[col].sum(min_count=1) if gk else last[col].sum(min_count=1)
    rule = spec[2]
    hit = (last[col] <= 0) if rule == "zero" else (last[col] <= last["reorder_level"])
    return hit.groupby([last[k] for k in gk], observed=True).sum() if gk else float(hit.sum())


def _items(F: Frame, d: pd.DataFrame) -> list:
    """What one stock item is: product, or product + store when the same product is counted in several stores."""
    if F.item_keys:
        return [k for k in F.item_keys if k in d.columns]
    return ["product_id"] if "product_id" in d.columns else []


def value(F: Frame, m: Metric, currency: str | None = None, mask: pd.Series | None = None) -> float | None:
    d = F.df[_mask(F, m, currency) & (mask if mask is not None else True)]
    if not len(d):
        return None
    if m.spec[0] in ("latest_level", "latest_count_if"):
        v = _latest(d, m.spec, None, _items(F, d))
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
        s = _latest(d, m.spec, "_p", _items(F, d))
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
        s = _latest(d, m.spec, col, [k for k in _items(F, d) if k != col])
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

"""A standard analysis frame per file: columns renamed by business concept, derived values added, master-list attributes
looked up through confirmed links. Every metric and chart is computed from these frames, so they work for any business."""
from __future__ import annotations
from dataclasses import dataclass, field
import re
import numpy as np
import pandas as pd
from ..model.concepts import CONCEPTS

NUMERIC_CANON = ["revenue", "gross_revenue", "cost", "expense", "profit", "discount", "discount_pct", "tax", "unit_price", "unit_cost", "money_other",
                 "quantity", "stock_level", "reorder_level", "margin_pct", "rating", "duration", "promised_duration", "age", "points", "activity_count", "percent",
                 "units_received", "units_ordered", "forecast", "competitor_price", "price_level", "trade_volume", "level_value"]
KEY_CANON = ["order_id", "customer_id", "product_id", "employee_id", "supplier_id", "site_id"]
MONEY = {c for c in NUMERIC_CANON if CONCEPTS[c].money}


@dataclass
class Frame:
    name: str
    role: str
    entity: str | None
    df: pd.DataFrame                      # canonical columns + original group columns + _t, _ok, _cur
    has_time: bool
    canon: dict[str, str] = field(default_factory=dict)       # canonical name -> source column
    groups: dict[str, list[str]] = field(default_factory=dict)  # group concept -> columns (original names)
    extra_numbers: list[tuple[str, str]] = field(default_factory=list)   # (column, concept) not used canonically
    currency: str | None = None           # main currency of money values (None = unknown / single)
    currencies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status_flags: list[tuple[str, str, str]] = field(default_factory=list)   # (status column, value, flag column)
    attributes: set = field(default_factory=set)                              # columns that describe a customer/product, not the row
    duration_unit: str = "days"
    nouns: dict = field(default_factory=dict)
    gaps: list = field(default_factory=list)                                  # derived 'days between two dates' columns
    item_keys: list = field(default_factory=list)                             # what one stock item is (product, or product + store)
    used_dates: set = field(default_factory=set)
    panel: str | None = None                                                  # one row per date per this column: rows are not sales

    def has(self, *names) -> bool:
        return all(n in self.df.columns and self.df[n].notna().any() for n in names)


def _primary(cols: dict, concept: str) -> str | None:
    hits = [(v["confidence"], c) for c, v in cols.items() if v["concept"] == concept]
    return max(hits)[1] if hits else None


def build_frame(p, model_cols: dict, file_info: dict, tables: dict | None = None, links: list | None = None, models: dict | None = None) -> Frame:
    src = p.df
    out = pd.DataFrame(index=src.index)
    has_time = "_t" in src.columns and src["_t"].notna().any()
    if has_time:
        out["_t"] = pd.to_datetime(src["_t"], errors="coerce")
    out["_ok"] = p.ok.values if p.ok is not None else True
    out["_row"] = src["_row"].values if "_row" in src.columns else np.arange(2, len(src) + 2)
    F = Frame(p.name, file_info.get("role", "other"), file_info.get("entity"), out, has_time)
    concept_cols = dict(model_cols)
    # columns borrowed from parents in a linked view carry their parent's concepts
    for s in (p.sources or [])[1:]:
        for c, v in ((models or {}).get(s, {}).get("columns", {}) or {}).items():
            if c in src.columns and c not in concept_cols:
                concept_cols[c] = v
    for canon in NUMERIC_CANON + KEY_CANON:
        c = _primary({k: v for k, v in concept_cols.items() if not (v.get("attribute_of") and CONCEPTS[v["concept"]].agg == "sum")}, canon)
        if canon == "price_level":                     # of open / high / low / close, the closing price is 'the price'
            pc = [k for k, v in concept_cols.items() if v["concept"] == "price_level"]
            c = next((k for rx in (r"^(?!.*adj).*close", r"adj", r"ltp|last", r"price") for k in pc if re.search(rx, str(k), re.I)), c)
        if c is not None and c in src.columns:
            vals = src[c]
            if canon in NUMERIC_CANON:
                num = pd.to_numeric(vals, errors="coerce")
                if num.notna().mean() < 0.5 * vals.notna().mean():
                    from ..understand.roles import clean_numeric
                    cn = clean_numeric(vals)
                    num = cn if cn is not None else num
                out[canon] = num
            else:
                out[canon] = vals.alpha.strip_string()
            F.canon[canon] = c
    # keys of entities that are usually few (warehouses, staff, suppliers) are also groups to compare
    for canon in ("site_id", "employee_id", "supplier_id"):
        c = F.canon.get(canon)
        if c and c in src.columns and 2 <= src[c].nunique(dropna=True) <= 200:
            out[c] = src[c].alpha.strip_string()
            F.groups.setdefault(canon, []).append(c)
    used = set(F.canon.values())
    for c, v in concept_cols.items():
        con = CONCEPTS[v["concept"]]
        if c not in src.columns:
            continue
        if con.kind == "group" and v["concept"] not in ("currency",):
            F.groups.setdefault(v["concept"], []).append(c)
            out[c] = src[c].alpha.strip_string()
        elif con.kind == "number" and c not in used:
            F.extra_numbers.append((c, "number" if v.get("attribute_of") else v["concept"]))
            if v.get("attribute_of"):
                F.attributes.add(c)
            out[c] = pd.to_numeric(src[c], errors="coerce")
        elif con.kind == "key" and c not in used:
            F.groups.setdefault(v["concept"], []).append(c)
            out[c] = src[c].alpha.strip_string()
    cur_col = _primary(concept_cols, "currency")
    if cur_col is not None:
        cv = concept_cols[cur_col]
        if cv.get("constant"):
            out["_cur"] = cv["constant"]
        elif cur_col in src.columns:
            out["_cur"] = src[cur_col].alpha.strip_string().str.upper()
    _movements(F, src, concept_cols)
    _date_roles(F, src, concept_cols, p, has_time)
    # time unit of the time-taken column, from its header
    dc = F.canon.get("duration") or F.canon.get("promised_duration")
    if dc:
        h = str(dc).lower()
        F.duration_unit = ("days" if h.startswith("days from") else "sec" if re.search(r"(^|[^a-z])sec|second", h) else "min" if re.search(r"(^|[^a-z])min", h)
                           else "hours" if re.search(r"hour|hrs|(^|[^a-z])hr", h) else "weeks" if re.search(r"week", h) else "months" if re.search(r"month", h) else "days")
    # other dates on the same row give gaps in days (booked -> appointment, order -> ship)
    if has_time:
        for c, v in concept_cols.items():
            if CONCEPTS[v["concept"]].kind == "date" and c in src.columns and c != p.time_col and c not in F.used_dates:
                d2 = pd.to_datetime(src[c], errors="coerce")
                gap = (out["_t"].dt.normalize() - d2.dt.normalize()).dt.days
                if gap.notna().mean() > 0.5 and gap.abs().median() <= 1100 and gap.abs().max() > 0:     # always 0: the same date twice
                    nz = gap[gap != 0]
                    if len(nz) and (nz < 0).mean() > 0.5:                # the other date mostly comes later (most same-day: judge by the rest)
                        gap = -gap
                    tname = p.time_col if p.time_col and not str(p.time_col).startswith("_") else "date"
                    name = f"days_between_{c}_and_{tname}".replace(" ", "_").lower()
                    out[name] = gap.astype(float)
                    F.extra_numbers.append((name, "number"))
                    F.gaps.append(name)
    F.item_keys = [k for k in (file_info.get("item_keys") or []) if k in src.columns]
    if F.item_keys:
        F.item_keys = ["product_id" if F.canon.get("product_id") == k else k for k in F.item_keys]
        for k in F.item_keys:
            if k not in out.columns and k in src.columns:
                out[k] = src[k].alpha.strip_string()
    _lookup_parents(F, p, tables or {}, links or [], models or {})
    _derive(F)
    F.status_flags = [(c, v, fc) for c, v, fc in getattr(p, "_rate_cols", []) if fc in src.columns]
    for c, v, fc in F.status_flags:
        out[fc] = src[fc].values
    if "_cur" in out.columns:
        money = next((m for m in ("revenue", "gross_revenue", "cost", "profit", "_stock_value", "unit_cost", "unit_price") if m in out.columns), None)
        if money:
            share = out.loc[out["_ok"].astype(bool)].groupby("_cur")[money].sum().sort_values(ascending=False)
            F.currencies = [str(x) for x in share.index if pd.notna(x)]
            F.currency = F.currencies[0] if F.currencies else None
        elif out["_cur"].notna().any():
            F.currency = str(out["_cur"].dropna().iloc[0]); F.currencies = [F.currency]
    F.nouns = _nouns(F, concept_cols)
    _drop_twins(F)
    F.panel = _panel(F)
    return F


def _drop_twins(F: Frame) -> None:
    """Two group columns that say the same thing (store_id and store_name, one name per id) would give every chart and
    finding twice. Keep the first, drop the twin from the groups (the column stays in the data)."""
    d = F.df
    order = [c for cols in F.groups.values() for c in cols if c in d.columns]
    drop = set()
    for i, a in enumerate(order):
        if a in drop:
            continue
        na = d[a].nunique()
        if na < 2 or na > 2000:
            continue
        for b in order[i + 1:]:
            if b in drop or b == a or d[b].nunique() != na:
                continue
            pair = d[[a, b]].dropna()
            if len(pair) and pair.groupby(a, observed=True)[b].nunique().max() == 1:
                drop.add(b)
    if drop:
        F.groups = {g: [c for c in cols if c not in drop] for g, cols in F.groups.items()}
        F.groups = {g: cols for g, cols in F.groups.items() if cols}


def _panel(F: Frame) -> str | None:
    """A daily (or weekly / monthly) table with one row per date per store, channel or source: its rows are slots in a grid,
    not sales, so 'number of rows' means nothing (every source has 730 rows because there are 730 days). Returns the
    grouping column, or None."""
    d = F.df
    if not F.has_time or F.role not in ("transactions", "periodic") or "_t" not in d.columns or len(d) < 30:
        return None
    if any(k in F.canon for k in ("order_id", "customer_id", "product_id")):
        return None
    day = d["_t"].dt.normalize()
    if day.nunique() < 10:
        return None
    if not day.duplicated().any():
        return "(date)"                                            # one row per date: period totals
    for c in [x for cols in F.groups.values() for x in cols if x in d.columns]:
        k = d[c]
        if 2 <= k.nunique() <= 200 and not pd.DataFrame({"t": day, "k": k}).duplicated().any():
            return c
    return None


NOUN_MAP = {"appt": "appointment", "appointment": "appointment", "booking": "booking", "invoice": "invoice", "inv": "invoice", "receipt": "sale",
            "bill": "bill", "ticket": "ticket", "txn": "transaction", "transaction": "transaction", "visit": "visit", "trip": "trip", "job": "job",
            "patient": "patient", "client": "client", "member": "member", "guest": "guest", "subscriber": "subscriber", "student": "student", "user": "user"}


def _nouns(F: Frame, concept_cols: dict) -> dict:
    """What the business calls its orders and customers (appointments and patients, invoices and subscribers...)."""
    out = {}
    for canon, key in (("order_id", "order"), ("customer_id", "customer")):
        c = F.canon.get(canon)
        if not c:
            continue
        for tok in re.split(r"[^a-z]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", str(c)).lower()):
            if tok in NOUN_MAP:
                out[key] = NOUN_MAP[tok]
                break
    return out


def relabel(text: str, nouns: dict) -> str:
    if not nouns or not text:
        return text
    o, c = nouns.get("order"), nouns.get("customer")
    if o:
        text = re.sub(r"\bOrders\b", o.capitalize() + "s", text); text = re.sub(r"\borders\b", o + "s", text)
        text = re.sub(r"\bOrder\b", o.capitalize(), text); text = re.sub(r"\border\b", o, text)
    if c:
        text = re.sub(r"\bCustomers\b", c.capitalize() + "s", text); text = re.sub(r"\bcustomers\b", c + "s", text)
        text = re.sub(r"\bCustomer\b", c.capitalize(), text); text = re.sub(r"\bcustomer\b", c, text)
    return text


MOVE_OUT = re.compile(r"^(out|outward|sale|sales|sold|issue|issued|dispatch|dispatched|consumption|consumed|stock out|transfer out)$", re.I)
MOVE_IN = re.compile(r"^(in|inward|receipt|received|grn|purchase|purchased|stock in|production|transfer in|opening|opening stock)$", re.I)
MOVE_LOSS = re.compile(r"damage|expired|expiry|wastage|waste|write ?off|writeoff|loss|lost|theft|shrink|scrap|spoil|broken", re.I)
MOVE_RETURN = re.compile(r"return", re.I)


def _movements(F: Frame, src: pd.DataFrame, concept_cols: dict) -> None:
    """A stock ledger (IN / OUT / Sale / Damaged ... with a quantity): split the quantity into units sold, received and lost."""
    mcol = _primary(concept_cols, "movement_type")
    if not mcol or "quantity" not in F.df.columns or mcol not in src.columns:
        return
    t = src[mcol].alpha.strip_string()
    q = F.df["quantity"]
    kind = pd.Series("other", index=src.index)
    kind[t.str.match(MOVE_OUT.pattern, case=False, na=False).astype(bool)] = "out"
    kind[t.str.match(MOVE_IN.pattern, case=False, na=False).astype(bool)] = "in"
    kind[t.str.contains(MOVE_RETURN.pattern, case=False, na=False).astype(bool)] = "return"
    kind[t.str.contains(MOVE_LOSS.pattern, case=False, na=False).astype(bool)] = "loss"
    signed = (q < 0).mean() > 0.15
    if (kind == "other").mean() > 0.5 and signed:       # no words, only signs: + is in, - is out
        kind = pd.Series(np.where(q < 0, "out", "in"), index=src.index)
    a = q.abs()
    src_q = F.canon["quantity"]
    F.df["quantity"] = a.where(kind == "out")
    F.df["units_received"] = a.where(kind == "in")
    F.df["_units_lost"] = a.where(kind == "loss")
    F.df["_units_returned"] = a.where(kind == "return")
    F.canon["units_received"] = f"{src_q} where {mcol} is an inward movement"
    F.canon["quantity"] = f"{src_q} where {mcol} is a sale / issue"
    F.canon["_units_lost"] = f"{src_q} where {mcol} is damaged / expired / lost"
    F.notes.append(f"'{mcol}' says which way stock moved: units sold, received, returned and lost (damaged/expired) are counted separately.")


def _date_roles(F: Frame, src: pd.DataFrame, concept_cols: dict, p, has_time: bool) -> None:
    """Dates other than the timeline: completed/received - order = time taken; due - order = time promised; expiry kept per row."""
    dd = {}
    for c, v in sorted(concept_cols.items(), key=lambda kv: -kv[1]["confidence"]):
        if CONCEPTS[v["concept"]].kind == "date" and c in src.columns and c != p.time_col:
            dd.setdefault(v["concept"], c)
    # several 'done' dates (shipped, then delivered): the last step is when the order was really completed,
    # so on-time is judged on delivery, not on dispatch
    dones = [c for c, v in concept_cols.items() if v["concept"] == "done_date" and c in src.columns and c != p.time_col]
    if len(dones) > 1:
        med = {c: pd.to_datetime(src[c], errors="coerce").dropna() for c in dones}
        med = {c: d.astype("int64").median() for c, d in med.items() if len(d) >= 0.3 * max(len(src), 1) * 0.1}
        if med:
            dd["done_date"] = max(med, key=med.get)
    ex = dd.get("expiry_date")
    if ex:
        F.df["_expiry"] = pd.to_datetime(src[ex], errors="coerce")
        F.used_dates.add(ex)
    if not has_time:
        return
    start = F.df["_t"].dt.normalize()
    done, due = dd.get("done_date"), dd.get("due_date")
    if done and "duration" not in F.df.columns:
        d = (pd.to_datetime(src[done], errors="coerce").dt.normalize() - start).dt.days
        if d.notna().mean() > 0.3 and d.median() >= 0:
            F.df["duration"] = d.astype(float)
            F.canon["duration"] = f"days from {p.time_col} to {done}"
            F.used_dates.add(done)
    if due and "promised_duration" not in F.df.columns:
        d = (pd.to_datetime(src[due], errors="coerce").dt.normalize() - start).dt.days
        if d.notna().mean() > 0.3 and d.median() >= 0:
            F.df["promised_duration"] = d.astype(float)
            F.canon["promised_duration"] = f"days from {p.time_col} to {due}"
            F.used_dates.add(due)


def _lookup_parents(F: Frame, p, tables: dict, links: list, models: dict) -> None:
    """Bring numeric attributes (unit cost, unit price, stock...) and concepts from master lists through used links."""
    for l in links:
        if not getattr(l, "use", False) or l.child != p.name or l.parent not in tables:
            continue
        P, pm = tables[l.parent], models.get(l.parent, {})
        if pm.get("file", {}).get("role") != "master":
            continue
        pcols = pm.get("columns", {})
        key = P.df[l.parent_col].alpha.strip_string()
        child_key = p.df[l.child_col].alpha.strip_string() if l.child_col in p.df.columns else None
        if child_key is None:
            continue
        for canon in ("unit_cost", "unit_price", "stock_level", "reorder_level"):
            c = _primary(pcols, canon)
            if c and canon not in F.df.columns:
                m = pd.Series(pd.to_numeric(P.df[c], errors="coerce").values, index=key.values)
                m = m[~m.index.duplicated()]
                F.df[canon] = child_key.map(m).values
                F.canon[canon] = f"{l.parent}.{c}"
                F.notes.append(f"{CONCEPTS[canon].label} looked up from {l.parent} through {l.child_col}.")
        ex = _primary(pcols, "expiry_date")
        if ex and "_expiry" not in F.df.columns and ex in P.df.columns:
            m = pd.Series(pd.to_datetime(P.df[ex], errors="coerce").values, index=key.values)
            m = m[~m.index.duplicated()]
            F.df["_expiry"] = child_key.map(m).values
            F.notes.append(f"Expiry dates looked up from {l.parent}.")
        for c, v in pcols.items():
            con = CONCEPTS[v["concept"]]
            if con.kind == "group" and c in F.df.columns and c not in sum(F.groups.values(), []):
                F.groups.setdefault(v["concept"], []).append(c)
            elif con.kind == "group" and c not in F.df.columns and v["concept"] not in ("currency",) and c in P.df.columns:
                m = pd.Series(P.df[c].alpha.strip_string().values, index=key.values)
                m = m[~m.index.duplicated()]
                F.df[c] = child_key.map(m).values
                F.groups.setdefault(v["concept"], []).append(c)


def _derive(F: Frame) -> None:
    d = F.df
    if "revenue" not in d and "gross_revenue" in d:
        net = d["gross_revenue"] - d.get("discount", 0)
        d["revenue"] = net
        F.canon["revenue"] = "gross sales minus discount" if "discount" in d else F.canon["gross_revenue"]
    if "revenue" not in d and {"quantity", "unit_price"} <= set(d.columns) and not d["quantity"].isna().all():
        d["revenue"] = d["quantity"] * d["unit_price"]
        F.canon["revenue"] = "units x unit price"
        F.notes.append("Revenue is calculated as units x unit price (there is no amount column).")
    if "cost" not in d and {"quantity", "unit_cost"} <= set(d.columns) and F.role not in ("master", "snapshot"):
        d["cost"] = d["quantity"] * d["unit_cost"]
        F.canon["cost"] = "units x unit cost"
        F.notes.append("Cost is calculated as units x unit cost.")
    if "profit" not in d and {"revenue", "cost"} <= set(d.columns):
        d["profit"] = d["revenue"] - d["cost"]
        F.canon["profit"] = "revenue minus cost"
    if {"duration", "promised_duration"} <= set(d.columns):
        d["_late"] = d["duration"] - d["promised_duration"]
        d["_on_time"] = (d["duration"] <= d["promised_duration"]).where(d["duration"].notna() & d["promised_duration"].notna())
    if "cost" not in d and "unit_cost" in d and ("units_received" in d or "units_ordered" in d) and "quantity" not in d:
        q = d["units_received"] if "units_received" in d and d["units_received"].notna().any() else d["units_ordered"]
        d["_purchase_value"] = q * d["unit_cost"]
        F.canon["_purchase_value"] = "units x unit cost"
    if "_units_lost" in d:
        d["_units_out_all"] = d.get("quantity", 0).fillna(0) + d["_units_lost"].fillna(0) if "quantity" in d else d["_units_lost"]
        d.loc[d["_units_out_all"] == 0, "_units_out_all"] = np.nan
    if {"forecast", "quantity"} <= set(d.columns):
        d["_fc_abs_err"] = (d["forecast"] - d["quantity"]).abs()
    if {"unit_price", "competitor_price"} <= set(d.columns):
        d["_price_gap"] = d["unit_price"] / d["competitor_price"].where(d["competitor_price"] > 0) - 1
    if "discount_pct" in d and d["discount_pct"].max() > 1.5:
        v = d["discount_pct"]
        nz = v[v.notna() & (v != 0)]
        if len(nz) and (nz > 1.5).mean() >= 0.5:
            d["discount_pct"] = v / 100.0                                  # written as percents: 10 means 10%
        else:
            # mostly written as shares (0.05) with a few percents (5): convert only those, row by row (reported by the data checks)
            d["discount_pct"] = v.where(~(v > 1.5), v / 100.0)
    if "discount_pct" in d and "revenue" in d and F.canon.get("revenue") == "units x unit price":
        d["revenue"] = d["revenue"] * (1 - d["discount_pct"].fillna(0))
        F.canon["revenue"] = "units x unit price x (1 - discount %)"
    if "price_level" in d and "_t" in d:
        keys = [k for k in ("ticker",) if k in d]
        tick = [c for c in sum(F.groups.values(), []) if c in d and F.groups.get("ticker") and c in F.groups["ticker"]]
        o = d.sort_values("_t")
        r = o.groupby(tick)["price_level"].pct_change() if tick else o["price_level"].pct_change()
        d["_ret"] = r.reindex(d.index)
    _customer_flags(F)
    if "_units_lost" in d and "unit_cost" in d:
        d["_lost_value"] = d["_units_lost"] * d["unit_cost"]
    if "stock_level" in d and "unit_cost" in d:
        d["_stock_value"] = d["stock_level"] * d["unit_cost"]
    elif "stock_level" in d and "unit_price" in d:
        d["_stock_value_retail"] = d["stock_level"] * d["unit_price"]
    if F.role == "snapshot":
        stock_cover(F)


def _customer_flags(F) -> None:
    """Per-row flags the customer metrics need: the customer's first purchase, and customers who have gone quiet
    (a regular buyer whose last purchase is more than twice their usual gap, and over 30 days, before the data ends)."""
    d = F.df
    if F.role not in ("transactions", "lines") or "customer_id" not in d or "_t" not in d or not d["_t"].notna().any():
        return
    ok = d["_ok"].astype(bool) if "_ok" in d else pd.Series(True, index=d.index)
    t = d["_t"].where(ok & d["customer_id"].notna())
    first = t.groupby(d["customer_id"]).transform("min")
    d["_first_order"] = (t.dt.normalize() == first.dt.normalize()) & t.notna()
    days = pd.DataFrame({"c": d["customer_id"], "day": t.dt.normalize()}).dropna().drop_duplicates()
    if days.empty:
        return
    days = days.sort_values(["c", "day"])
    gap = days.groupby("c")["day"].diff().dt.days
    usual = gap.groupby(days["c"]).median()
    visits = days.groupby("c").size()
    last = days.groupby("c")["day"].max()
    end = t.max().normalize()
    since = (end - last).dt.days
    quiet = (visits >= 3) & (since > np.maximum(2 * usual.reindex(last.index), 30))
    d["_cust_quiet"] = d["customer_id"].map(quiet).fillna(False).astype(bool)


def stock_cover(F) -> None:
    """For a stock panel that also records units sold: days of stock left, dead stock and overstock per item, on the latest
    row of each item only (so an average or a sum over rows is an average or sum over items)."""
    d = F.df
    if not {"stock_level", "quantity", "_t"} <= set(d.columns) or not d["_t"].notna().any():
        return
    items = [k for k in (F.item_keys or (["product_id"] if "product_id" in d else [])) if k in d]
    if not items:
        return
    end = d["_t"].max()
    recent = d[d["_t"] > end - pd.Timedelta(days=90)]
    days = max(1, (end - max(recent["_t"].min(), end - pd.Timedelta(days=90))).days + 1)
    sold = recent.groupby(items, observed=True)["quantity"].sum()
    latest_idx = d.sort_values("_t").groupby(items, observed=True).tail(1).index
    lat = d.loc[latest_idx, items + ["stock_level"]].copy()
    key = pd.MultiIndex.from_frame(lat[items]) if len(items) > 1 else lat[items[0]]
    s = sold.reindex(key).to_numpy() if len(items) > 1 else sold.reindex(lat[items[0]]).to_numpy()
    rate = np.nan_to_num(s, nan=0.0) / days
    cover = np.where(rate > 0, lat["stock_level"].to_numpy() / np.where(rate > 0, rate, 1), np.inf)
    d["_cover_days"] = np.nan
    d.loc[latest_idx, "_cover_days"] = np.where(np.isfinite(cover), cover, np.nan)
    if "_stock_value" in d:
        val = d.loc[latest_idx, "_stock_value"].to_numpy()
        dead = (lat["stock_level"].to_numpy() > 0) & (np.nan_to_num(s, nan=0.0) <= 0)
        over = np.isfinite(cover) & (cover > 180)
        d["_dead_value"] = np.nan; d["_over_value"] = np.nan
        d.loc[latest_idx, "_dead_value"] = np.where(dead, val, 0.0)
        d.loc[latest_idx, "_over_value"] = np.where(over, val, 0.0)

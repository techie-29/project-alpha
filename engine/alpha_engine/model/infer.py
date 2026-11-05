"""Work out what each column means for the business, mostly from the data itself.

Evidence, combined into one score per (column, concept):
  1. value shape   - ranges, whole numbers, decimals, negatives, known value sets (currencies, genders, status words...)
  2. arithmetic    - columns that are exact functions of others: qty x price = amount, sales - cost = profit, ...
  3. structure     - what kind of file it is (log, master list, stock snapshot); levels vs flows
  4. names         - fuzzy match of the header (and file name) against synonyms; one signal among several
  5. memory        - what the owner confirmed for a similar column before
The owner's confirmation always wins. Nothing here needs the AI; the AI only reviews low-confidence columns (see review.py)."""
from __future__ import annotations
import itertools
import re
from difflib import SequenceMatcher
import numpy as np
import pandas as pd
from .concepts import (CONCEPTS, NUMBER_CONCEPTS, KEY_CONCEPTS, GROUP_CONCEPTS, DATE_CONCEPTS, STATUS_WORDS, CHANNEL_WORDS,
                       PAYMENT_WORDS, MOVEMENT_WORDS, TICKER_VALUE, GENDER_VALUES, CURRENCIES, REGION_WORDS, SENTIMENT_WORDS, YES_NO_VALUES, ID_HEAD, PERSON_NAME, ALWAYS_PII, ID_VALUE)

from ..understand.roles import id_header

FEW_ENTITY_KEYS = {"site_id", "employee_id", "supplier_id"}
LOCATION_TOKEN = re.compile(r"(^|_|\s)(city|state|country|region|zone|district|province|postal|zip|pincode|pin_code|territory)($|_|\s|code)", re.I)     # entities that are often few (6 warehouses, 12 staff)


def is_pii(col: str) -> bool:
    return bool(PERSON_NAME.search(col) or ALWAYS_PII.search(col))
W_NAME, W_VALUE = 0.5, 0.5
SAMPLE = 4000


# ---------------- names ----------------
def tokens(name: str) -> list[str]:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(name))
    s = s.replace("#", " number ").replace("№", " number ").replace("°", " ")
    s = re.sub(r"%", " pct ", s)
    return [t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if t]


# abbreviations found in real exports. Both sides are mapped to the full word before comparing, so 'Net Amt' matches 'net amount'
# and 'Qty Ordered' still matches the synonym 'qty ordered'.
ABBR = {"amt": "amount", "qty": "quantity", "qnty": "quantity", "qtty": "quantity", "disc": "discount", "dis": "discount", "val": "value", "cust": "customer",
        "prod": "product", "desc": "description", "avg": "average", "tot": "total", "inv": "invoice", "txn": "transaction", "trx": "transaction",
        "dt": "date", "yr": "year", "pct": "percent", "perc": "percent", "no": "number", "num": "number", "nr": "number", "rev": "revenue",
        "cat": "category", "subcat": "subcategory", "dept": "department", "wh": "warehouse", "loc": "location", "pmt": "payment", "pymt": "payment",
        "exp": "expiry", "mfg": "manufacturing", "sp": "selling", "cp": "cost", "mrp": "mrp", "uom": "unit", "pcs": "pieces", "emp": "employee",
        "supp": "supplier", "vend": "vendor", "px": "price", "prc": "price", "nm": "name", "cd": "code", "ord": "order", "ship": "shipping", "del": "delivery", "chg": "charge", "chrg": "charge"}


def _canon(x: str) -> str:
    return ABBR.get(x, x)


def _eq(t: str, u: str) -> bool:
    """t = synonym token, u = header token. Allows known abbreviations (amt = amount), short forms in the header (cust ~ customer),
    plurals (unit ~ units) and small typos, but not near-words (plan != plant, counter != country) or a synonym being a mere
    prefix of a longer header word (sales != salesperson)."""
    if t == u or _canon(t) == _canon(u):
        return True
    if min(len(t), len(u)) >= 3 and (t in (u + "s", u + "es") or u in (t + "s", t + "es")):
        return True
    if len(u) >= 3 and t.startswith(u) and len(t) - len(u) >= 2 and len(u) >= 0.4 * len(t):
        return True
    if len(t) >= 4 and u.startswith(t) and 1 <= len(u) - len(t) <= 3 and u[len(t):] in ("s", "es", "ed", "d", "ing"):
        return True
    return min(len(t), len(u)) >= 5 and SequenceMatcher(None, t, u).ratio() >= 0.86


# one-word synonyms so common that they say little on their own ('Type', 'Total', 'Amount', 'Value'): a match counts less
GENERIC = {"type", "class", "total", "amount", "value", "rate", "item", "line", "name", "group", "kind", "mode", "level", "index", "balance", "score", "share", "days", "bill"}


QUALIFIERS = {"amount", "amt", "value", "val", "total", "monthly", "daily", "weekly", "yearly", "annual", "rs", "inr", "usd", "eur", "gbp", "aed", "sgd",
              "aud", "cad", "in", "of", "the", "current", "curr"}


def name_score(col: str, synonyms) -> tuple[float, str | None]:
    nt = tokens(col)
    if not nt:
        return 0.0, None
    whole = " ".join(nt)
    best, why = 0.0, None
    for syn in synonyms:
        st = syn.split()
        hit = sum(1 for t in st if any(_eq(t, u) for u in nt))
        if not hit:
            continue
        cov = hit / len(st)
        content = [u for u in nt if u not in QUALIFIERS] or nt          # 'gst amount', 'budget inr', 'monthly salary': the qualifier explains nothing
        expl_c = sum(1 for u in content if any(_eq(t, u) for t in st)) / len(content)
        expl = expl_c if expl_c > 0 else sum(1 for u in nt if any(_eq(t, u) for t in st)) / len(nt)   # 'Final Amount' still matches 'amount' as before
        sc = cov * (0.3 + 0.7 * expl) * (1.0 if cov == 1 else 0.8)
        r = SequenceMatcher(None, whole, syn).ratio()
        if r > 0.86:
            sc = max(sc, r)
        if len(st) == 1 and st[0] in GENERIC:
            sc *= 0.6
        if sc > best:
            best, why = sc, syn
    return min(best, 1.0), why


# ---------------- value evidence ----------------
def num_stats(s: pd.Series) -> dict | None:
    v = pd.to_numeric(s, errors="coerce").dropna()
    if len(v) < 2:
        return None
    if len(v) > SAMPLE:
        v = v.sample(SAMPLE, random_state=0)
    a = v.to_numpy(dtype=float)
    frac = np.abs(a - np.round(a))
    dec2 = np.abs(a * 100 - np.round(a * 100)) < 1e-6
    return {"n": len(a), "int": float((frac < 1e-9).mean()), "dec2": float((dec2 & (frac > 1e-9)).mean()), "neg": float((a < 0).mean()),
            "zero": float((a == 0).mean()), "min": float(a.min()), "max": float(a.max()), "med": float(np.median(a)), "nu": int(len(np.unique(a)))}


def cat_stats(s: pd.Series) -> dict:
    v = s.dropna().astype(str).str.strip()
    vc = v.value_counts()
    top = list(vc.index[:60])
    return {"nu": int(v.nunique()), "n": int(len(v)), "vals": top, "len": float(v.str.len().mean()) if len(v) else 0.0}


def value_score(cid: str, st: dict | None, cs: dict | None) -> tuple[float, str | None]:
    """(score 0..1, reason). score 0 = values rule this concept out."""
    c = CONCEPTS[cid]
    if c.kind == "number":
        if st is None:
            return 0.0, None
        pos = st["neg"] <= 0.02
        if cid in ("revenue", "gross_revenue", "cost", "expense", "money_other", "unit_price", "unit_cost", "competitor_price", "price_level", "refund", "stock_value"):
            if not pos and cid != "money_other":
                return 0.15, "has negative values"
            sc = 0.45 + (0.3 if st["dec2"] >= 0.4 else 0.15 if st["med"] >= 20 else 0.0)
            return sc, "positive amounts" + (" with cents" if st["dec2"] >= 0.4 else "")
        if cid in ("discount", "tax"):
            if cid == "discount" and st["max"] <= 1 and st["int"] < 0.98:
                return 0.1, "all values are below 1: a share, not an amount"
            return (0.55 if pos else 0.1), ("non-negative amounts, often zero" if st["zero"] > 0.2 else "non-negative amounts")
        if cid == "profit":
            return (0.75 if 0.005 < st["neg"] < 0.6 else 0.45), ("can be negative, like profit" if st["neg"] > 0.005 else "amounts")
        if cid == "quantity":
            if st["int"] < 0.97:
                return 0.05, "not whole numbers"
            return (0.75 if st["min"] >= 0 and st["med"] <= 1000 else 0.35), "small whole numbers"
        if cid in ("units_received", "units_ordered", "units_returned", "on_order"):
            if st["int"] < 0.97 or st["neg"] > 0.02:
                return 0.05, None
            return 0.6, "whole non-negative counts"
        if cid == "trade_volume":
            return (0.6 if st["int"] > 0.97 and st["med"] >= 1000 else 0.15), "large whole numbers (traded volume)" if st["med"] >= 1000 else None
        if cid in ("forecast", "level_value"):
            return 0.4, None
        if cid in ("stock_level", "reorder_level"):
            return (0.55 if st["int"] >= 0.9 and st["neg"] <= 0.05 else 0.15), "whole non-negative counts"
        if cid == "margin_pct":
            if st["max"] > 1000 or st["int"] > 0.98:
                return 0.05, None
            in1, in100 = st["min"] >= -1.5 and st["max"] <= 1.5, st["min"] >= -150 and st["max"] <= 150
            return (0.7 if (in1 or in100) else 0.1), "a percentage range"
        if cid == "rating":
            # a rating lives on a scale like 1-5 or 0-10. Values that are all below 1 (0.05, 0.1) are shares, not ratings.
            if st["min"] < 0 or st["max"] > 10 or st["max"] <= 1 or st["nu"] > 101:
                return 0.0, None
            return (0.85 if st["max"] <= 5 else 0.6), f"values between {st['min']:g} and {st['max']:g}"
        if cid in ("duration", "promised_duration"):
            if st["neg"] > 0.02 or st["max"] > 2000:
                return 0.05, None
            return (0.6 if st["int"] > 0.8 else 0.45), "small non-negative durations"
        if cid == "age":
            ok = st["int"] > 0.95 and st["min"] >= 0 and st["max"] <= 120 and 12 <= st["med"] <= 85
            return (0.85 if ok else 0.0), "whole numbers in a human age range" if ok else None
        if cid in ("points", "activity_count"):
            return (0.5 if st["int"] > 0.95 and st["neg"] <= 0.01 else 0.1), "whole non-negative counts"
        if cid == "discount_pct":
            ok = st["min"] >= 0 and (st["max"] <= 1 or st["max"] <= 100) and (st["int"] < 0.98 or st["max"] <= 1)
            return (0.6 if ok else 0.05), "a share between 0 and 1 (or 100)" if ok else None
        if cid == "percent":
            ok = (st["min"] >= 0 and st["max"] <= 100) or (st["min"] >= 0 and st["max"] <= 1)
            return (0.5 if ok else 0.0), "between 0 and 100" if ok else None
        if cid == "number":
            return 0.3, None
        return 0.3, None
    if c.kind == "group":
        if cs is None:
            return 0.0, None
        vals = cs["vals"]
        frac = lambda rx: sum(1 for v in vals if rx.search(v)) / max(len(vals), 1)
        if cid == "currency":
            ok = vals and all(v.upper() in CURRENCIES for v in vals)
            return (0.97 if ok else 0.0), "values are currency codes" if ok else None
        if cid == "gender":
            ok = vals and all(v.lower() in GENDER_VALUES for v in vals)
            return (0.95 if ok else 0.0), "values are genders" if ok else None
        if cid == "status":
            f = frac(STATUS_WORDS)
            return (0.9 if f >= 0.5 else 0.15), "values look like outcomes (completed, cancelled...)" if f >= 0.5 else None
        if cid == "channel":
            f = frac(CHANNEL_WORDS)
            return (0.85 if f >= 0.5 else 0.2), "values look like sales channels" if f >= 0.5 else None
        if cid == "payment_method":
            f = frac(PAYMENT_WORDS)
            return (0.85 if f >= 0.5 else 0.15), "values look like payment methods" if f >= 0.5 else None
        if cid == "location":
            f = frac(REGION_WORDS)
            return (0.8 if f >= 0.5 else 0.35), "values look like regions" if f >= 0.5 else None
        if cid == "sentiment":
            f = frac(SENTIMENT_WORDS)
            return (0.9 if f >= 0.6 else 0.1), "values are positive / negative / neutral" if f >= 0.6 else None
        if cid == "movement_type":
            f = sum(1 for v in vals if MOVEMENT_WORDS.match(v.strip())) / max(len(vals), 1)
            return (0.92 if f >= 0.5 else 0.05), "values are stock movements (IN, OUT, Sale, Damaged...)" if f >= 0.5 else None
        if cid == "ticker":
            f = sum(1 for v in vals if TICKER_VALUE.match(v)) / max(len(vals), 1)
            return (0.5 if f >= 0.9 and 2 <= cs["nu"] <= 3000 else 0.05), "short upper-case codes like share symbols" if f >= 0.9 else None
        if cid == "yes_no":
            ok = vals and all(v.lower() in YES_NO_VALUES for v in vals)
            return (0.85 if ok else 0.0), "yes / no values" if ok else None
        if cid == "name_label":
            return (0.45 if cs["nu"] >= 10 else 0.1), None
        if cid == "reason":
            return (0.4 if cs["nu"] <= 40 else 0.1), None
        if cid == "group":
            return 0.3, None
        return (0.35 if cs["nu"] <= 200 else 0.15), None
    if c.kind == "key":
        if cs is None:
            return 0.0, None
        coded = sum(1 for v in cs["vals"] if ID_VALUE.match(v)) / max(len(cs["vals"]), 1)
        if cs["nu"] >= 2 and coded >= 0.8:
            return (0.75 if cid == "entity_id" else 0.6), "values are codes like " + cs["vals"][0]
        return (0.5 if cs["nu"] >= 20 else 0.1), "many distinct codes" if cs["nu"] >= 20 else None
    if c.kind == "date":
        return (0.75 if cid == "event_date" else 0.5), None
    if c.kind == "text":
        if cid == "free_text":
            return (0.7 if cs and cs["len"] > 25 else 0.1), "long free text" if cs and cs["len"] > 25 else None
        return 0.3, None
    return 0.0, None


def candidates_for(role: str, info: dict, col: str = "") -> list:
    if role == "measure":
        return NUMBER_CONCEPTS
    if role == "id":
        return KEY_CONCEPTS + [CONCEPTS["personal"], CONCEPTS["location"], CONCEPTS["name_label"]]
    if role == "category":
        out = GROUP_CONCEPTS[:]
        keyish = bool(ID_HEAD.search(col)) or id_header(col) or len(tokens(col)) == 1
        out += [k for k in KEY_CONCEPTS if k.id in FEW_ENTITY_KEYS or ((keyish or k.id == "entity_id") and info.get("unique", 0) >= 20)]
        return out + [CONCEPTS["personal"], CONCEPTS["free_text"]]
    if role == "flag":
        return GROUP_CONCEPTS
    if role == "time":
        return DATE_CONCEPTS
    if role == "text":
        return [CONCEPTS["personal"], CONCEPTS["free_text"], CONCEPTS["location"], CONCEPTS["name_label"]] + KEY_CONCEPTS
    return []


# ---------------- arithmetic links between columns ----------------
def find_identities(df: pd.DataFrame, cols: list[str], max_cols: int = 16) -> list[dict]:
    """Columns that are (almost) exact functions of others, on >= 90% of rows."""
    cols = cols[:max_cols]
    if len(cols) < 3:
        return []
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 20:
        return []
    if len(X) > 3000:
        X = X.sample(3000, random_state=0)
    A = {c: X[c].to_numpy(float) for c in cols}
    close = lambda x, y: float((np.abs(x - y) <= 0.011 * np.abs(y) + 0.02).mean())
    out = []
    nonconst = [c for c in cols if np.nanstd(A[c]) > 0]
    for a, b in itertools.combinations(nonconst, 2):
        for c in nonconst:
            if c in (a, b):
                continue
            m = close(A[a] * A[b], A[c])
            if m >= 0.9:
                out.append({"type": "product", "cols": [a, b, c], "match": m, "text": f"{a} x {b} = {c}"})
    for a, b in itertools.permutations(nonconst, 2):
        for c in nonconst:
            if c in (a, b):
                continue
            m = close(A[a] - A[b], A[c])
            if m >= 0.9 and np.mean(np.abs(A[b])) > 0:
                out.append({"type": "difference", "cols": [a, b, c], "match": m, "text": f"{a} - {b} = {c}"})
            with np.errstate(divide="ignore", invalid="ignore"):
                r = np.where(A[b] != 0, A[a] / A[b], np.nan)
            ok = np.isfinite(r)
            if ok.mean() > 0.8:
                for k in (1.0, 100.0):
                    m = close(r[ok] * k, A[c][ok])
                    if m >= 0.9:
                        out.append({"type": "ratio", "cols": [a, b, c], "scale": k, "match": m, "text": f"{a} / {b}{' x 100' if k == 100 else ''} = {c}"})
    money = [c for c in nonconst if np.mean(np.abs(A[c] * 100 - np.round(A[c] * 100)) < 1e-6) > 0.9][:12]
    if len(money) >= 4:
        for a, b, c in itertools.permutations(money, 3):
            if b > c:
                continue
            for d in money:
                if d in (a, b, c):
                    continue
                m = close(A[a] - A[b] + A[c], A[d])
                if m >= 0.9:
                    out.append({"type": "net", "cols": [a, b, c, d], "match": m, "text": f"{a} - {b} + {c} = {d}"})
    # drop identities implied by a stronger one (e.g. difference a-b=c and a-c=b both appear)
    seen, uniq = set(), []
    for i in sorted(out, key=lambda x: -x["match"]):
        key = (i["type"], frozenset(i["cols"]))
        if key in seen:
            continue
        seen.add(key); uniq.append(i)
    return uniq[:30]


def identity_hints(ids: list[dict], st: dict, nscore) -> dict[str, dict[str, tuple[float, str]]]:
    """Turn identities into concept bonuses: {col: {concept: (bonus, reason)}}."""
    h: dict[str, dict[str, tuple[float, str]]] = {}
    add = lambda col, cid, b, why: h.setdefault(col, {}).__setitem__(cid, max(h.get(col, {}).get(cid, (0, ""))[0], b) == b and (b, why) or h[col][cid])
    for i in ids:
        cs = i["cols"]
        if i["type"] == "product":
            a, b, c = cs
            qa, qb = st.get(a, {}) or {}, st.get(b, {}) or {}
            frac01 = [x for x, q in ((a, qa), (b, qb)) if q.get("min", -1) >= 0 and q.get("max", 9) <= 1 and q.get("int", 1) < 0.98]
            if frac01:                                        # rate x base = part  (discount % x gross = discount)
                r = frac01[0]
                kind = max(("discount", "tax"), key=lambda k: nscore(c, k) + nscore(r, k))
                add(r, "discount_pct" if kind == "discount" else "percent", 0.3, f"{i['text']}: a share applied to an amount")
                add(c, kind, 0.3, f"{i['text']}: a share of an amount")
                continue
            qty, price = (a, b) if (qa.get("int", 0), -qa.get("med", 0)) >= (qb.get("int", 0), -qb.get("med", 0)) else (b, a)
            if (st.get(qty) or {}).get("int", 0) < 0.97:
                continue
            costish = nscore(price, "unit_cost") > nscore(price, "unit_price") or nscore(c, "cost") > nscore(c, "revenue")
            target = max(("revenue", "gross_revenue", "cost", "expense"), key=lambda k: nscore(c, k)) if max(nscore(c, k) for k in ("revenue", "gross_revenue", "cost", "expense")) >= 0.5 else ("cost" if costish else "revenue")
            add(qty, "quantity", 0.35, f"{i['text']}: looks like units x price")
            add(price, "unit_cost" if costish else "unit_price", 0.35, f"{i['text']}: looks like a price per unit")
            add(c, target, 0.3, f"{i['text']}: an amount made of units x price")
        elif i["type"] == "difference":
            a, b, c = cs
            if nscore(b, "discount") >= 0.5:
                add(a, "gross_revenue", 0.35, f"{i['text']}: amount before discount"); add(b, "discount", 0.35, i["text"]); add(c, "revenue", 0.3, f"{i['text']}: amount after discount")
            elif (st.get(c) or {}).get("neg", 0) > 0.005 or nscore(c, "profit") >= 0.5:
                add(a, "revenue", 0.3, f"{i['text']}: what is earned"); add(b, "cost", 0.35, f"{i['text']}: what is paid out"); add(c, "profit", 0.4, f"{i['text']}: earnings minus cost")
        elif i["type"] == "net":
            a, b, c, d = cs
            add(a, "gross_revenue", 0.3, f"{i['text']}: starting amount"); add(b, "discount", 0.3, f"{i['text']}: taken off"); add(d, "revenue", 0.35, f"{i['text']}: final amount")
            add(c, "tax" if nscore(c, "tax") >= nscore(c, "expense") else "expense", 0.25, f"{i['text']}: added on")
        elif i["type"] == "ratio":
            a, b, c = cs
            if nscore(a, "profit") >= 0.5 or (st.get(a) or {}).get("neg", 0) > 0.005:
                add(c, "margin_pct", 0.45, f"{i['text']}: profit as a share of sales"); add(a, "profit", 0.2, i["text"]); add(b, "revenue", 0.2, i["text"])
    return h


# ---------------- file structure ----------------
FILE_HINTS = {"snapshot": ("stock", "inventory", "warehouse stock", "on hand", "stock levels", "inventory snapshot"),
              "transactions": ("orders", "sales", "transactions", "invoices", "bookings", "order items", "line items", "payments", "visits", "tickets"),
              "customer": ("customers", "customer master", "clients", "members", "patients", "accounts"),
              "product": ("products", "product catalog", "catalogue", "items", "sku master", "menu", "services"),
              "purchase": ("purchase", "purchases", "purchase orders", "purchase order", "po", "procurement", "grn", "goods received", "inward", "supplier orders", "buying"),
              "supplier": ("suppliers", "vendors"), "employee": ("employees", "staff", "agents"), "site": ("stores", "branches", "outlets", "warehouses", "sites"),
              "expense": ("expenses", "expense", "costs", "opex", "overheads", "operating costs", "expenses vs budget", "spend")}


def file_name_hint(fname: str) -> dict[str, float]:
    if " › " in fname:                                  # 'Book.xlsx › Sheet': the sheet says what this table is
        fname = fname.split(" › ", 1)[1]
    base = re.sub(r"\.(csv|xlsx|xls)$", "", fname, flags=re.I)
    return {k: name_score(base, v)[0] for k, v in FILE_HINTS.items()}


STOCK_NAME = ("stock", "on hand", "inventory", "closing stock", "stock level", "balance qty", "soh", "qoh", "available qty", "inventory level", "current stock", "in stock")


LEVEL_OK = ("quantity", "activity_count", "number", "points", "stock_level", "units_ordered", "units_received", "on_order", "level_value", "price_level",
            "stock_value", "reorder_level", "unit_price", "unit_cost", "competitor_price")


def level_columns(df: pd.DataFrame, item_keys: list, concept_of: dict) -> list[str]:
    """Number columns that behave like a running count for each item (today's value is close to yesterday's), or are named so.
    Flows (units sold per day) jump around; levels (stock on hand, balance, price) move smoothly."""
    nums = [c for c, k in concept_of.items() if c in df.columns and CONCEPTS[k].kind == "number" and c not in item_keys
            and (k in LEVEL_OK or name_score(c, STOCK_NAME)[0] >= 0.6)]
    out = []
    d = df[item_keys + ["_t"] + nums].dropna(subset=["_t"]).sort_values(item_keys + ["_t"])
    for c in nums:
        if name_score(c, STOCK_NAME)[0] >= 0.6 or concept_of[c] in ("stock_level", "price_level", "level_value"):
            out.append(c); continue
        v = pd.to_numeric(d[c], errors="coerce")
        prev = v.groupby([d[k] for k in item_keys], observed=True).shift(1) if item_keys else v.shift(1)
        ok = v.notna() & prev.notna()
        if ok.sum() < 30 or v[ok].std() == 0:
            continue
        r = float(np.corrcoef(v[ok], prev[ok])[0, 1])
        step = float(np.median(np.abs(v[ok] - prev[ok])) / max(np.median(np.abs(v[ok])), 1e-9))
        if r >= 0.7 and step <= 0.25:
            out.append(c)
    return out


def file_role(p, concept_of: dict[str, str], fhint: dict[str, float]) -> dict:
    df, n = p.df, len(p.df)
    keys = [c for c, k in concept_of.items() if CONCEPTS[k].kind == "key" and c in df.columns]
    if p.kind == "summary":
        return {"role": "summary", "entity": None, "reason": "a few summary rows"}
    ENT = {"customer_id": "customer", "product_id": "product", "supplier_id": "supplier", "employee_id": "employee", "site_id": "site"}
    flows = set(concept_of.values()) & {"revenue", "gross_revenue", "quantity", "profit", "order_id", "discount", "refund", "units_returned", "activity_count"}
    for c in keys:
        if concept_of[c] in ENT and p.time_col is not None and not flows:
            vals = df[c].dropna()
            if len(vals) >= 2 and vals.nunique() == len(vals) and (id_header(c) or ID_HEAD.search(c)) and len(vals) >= 0.95 * n:
                ent = ENT[concept_of[c]]
                return {"role": "master", "entity": ent, "key": c, "dated_master": True,
                        "reason": f"one row per {ent} ({c} is unique); its dates ({p.time_col}) describe each {ent}, they are not events"}
    if p.time_col is None:
        oid = [c for c in keys if concept_of[c] == "order_id"]
        if oid and df[oid[0]].nunique() < 0.95 * df[oid[0]].notna().sum():
            return {"role": "lines", "entity": "order line", "key": oid[0], "reason": f"several rows per {oid[0]}: the lines of each order"}
        for c in keys:
            u = df[c].nunique(dropna=True)
            if u >= 0.98 * df[c].notna().sum() and (u >= 5 or (u >= 2 and (id_header(c) or ID_HEAD.search(c)))):     # 3 stores with a store_id are a list
                ent = CONCEPTS[concept_of[c]].entity
                best = max(("customer", "product", "supplier", "employee", "site"), key=lambda e: fhint.get(e, 0))
                if fhint.get(best, 0) >= 0.6:
                    ent = best
                return {"role": "master", "entity": ent, "key": c, "reason": f"one row per {ent} ({c} is unique) and no dates"}
        oid = [c for c in keys if concept_of[c] == "order_id"]
        if oid and df[oid[0]].nunique() < 0.95 * df[oid[0]].notna().sum():
            return {"role": "lines", "entity": "order line", "key": oid[0], "reason": f"several rows per {oid[0]}: the lines of each order"}
        return {"role": "reference", "entity": None, "reason": "no dates and no unique key"}
    t = df["_t"]
    ledger = any(k == "movement_type" for k in concept_of.values())       # IN / OUT / Sale rows: a log of movements, never a snapshot
    singles = [c for c in keys if concept_of[c] != "order_id"] if not ledger else []
    extra = [c for c, k in concept_of.items() if c in df.columns and c not in singles and 2 <= df[c].nunique() <= 200 and
             (k in ("site_id", "location") or (CONCEPTS[k].kind == "group" and k not in ("status", "movement_type", "yes_no", "reason", "sentiment")))]
    for ks in [[c] for c in singles] + [[a, b] for a in singles for b in extra + singles if b != a]:
        g = df[ks].assign(_d=t.dt.normalize()).dropna()
        if len(g) < 20:
            continue
        per = g.groupby(ks)["_d"].nunique()
        nd = g["_d"].nunique()
        dup = g.duplicated().mean()
        coverage = g.groupby("_d").size().mean() / max(len(per), 1)      # share of all items seen on a typical date
        if per.median() >= 3 and dup <= 0.05 and nd <= 0.5 * len(g) and len(per) >= 3 and coverage >= 0.5:
            lev = level_columns(df, ks, concept_of)
            if not lev and fhint.get("snapshot", 0) >= 0.6:   # the file is called 'inventory' / 'stock': its whole-number counts are the levels
                lev = [c for c, k in concept_of.items() if c in df.columns and CONCEPTS[k].kind == "number" and c not in ks
                       and (pd.to_numeric(df[c], errors="coerce").dropna() % 1 == 0).all()]
            if not lev:
                continue                                                # the same items every day, but nothing that behaves like a stock count
            ent = CONCEPTS[concept_of[ks[0]]].entity
            return {"role": "snapshot", "entity": ent, "key": ks[0], "item_keys": ks, "levels": lev,
                    "reason": f"the same {' + '.join(ks)} appears once per date across {nd} dates, and {', '.join(lev[:2])} behaves like a running count (a stock snapshot)"}
    if p.kind == "periodic" and any(concept_of[c] in ("customer_id", "product_id", "order_id") and df[c].nunique() >= 20 for c in keys):
        return {"role": "transactions", "entity": "order", "reason": "dated rows naming customers or products: a log of events"}
    if p.kind == "periodic":
        return {"role": "periodic", "entity": None, "reason": "about one row per date (period totals)"}
    return {"role": "transactions", "entity": "order", "reason": "dated rows, one per event or line"}


def _set(v: dict, cid: str, reason: str, conf: float = 0.7) -> None:
    if v.get("source") in ("owner", "memory"):
        return
    v.update(concept=cid, label=CONCEPTS[cid].label, confidence=max(v["confidence"], conf), reasons=[reason] + v["reasons"][:2])


TICKER_HEAD = re.compile(r"^[A-Z][A-Z0-9&\-]{0,9}$")
PRICE_PART = re.compile(r"(open|high|low|close|adj|adjusted|ltp|vwap|price|nav)", re.I)


def _stock_and_market_rules(df, p, cols: dict, nst: dict, role: dict, fhint: dict) -> None:
    """Business-structure rules that names alone get wrong: purchases are costs, round 0-100 'discounts' are percentages,
    share prices are levels (never added up), dates after the data ends are expiries or due dates."""
    con = lambda c: cols[c]["concept"]
    # 1. purchase files: what is paid is a cost, not a sale
    has = {v["concept"] for v in cols.values()}
    purchase = fhint.get("purchase", 0) >= 0.6 or ("supplier_id" in has and has & {"units_ordered", "units_received"} and "customer_id" not in has)
    if purchase:
        for c, v in cols.items():
            if v["concept"] in ("unit_price",):
                _set(v, "unit_cost", "a rate in a purchase file is what each unit costs you")
            elif v["concept"] in ("revenue", "gross_revenue"):
                _set(v, "cost", "an amount in a purchase file is money paid to suppliers")
            elif v["concept"] == "quantity" and not (has & {"units_ordered", "units_received"}):
                _set(v, "units_received", "units in a purchase file are units bought")
    # 2. 'Discount' holding round numbers 0..100 (0, 5, 10, 15, 20): a percentage, not an amount
    for c, v in cols.items():
        st = nst.get(c)
        if v["concept"] == "discount" and st and st["min"] >= 0 and st["max"] <= 100 and st["int"] >= 0.98 and st["nu"] <= 21:
            vals = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(vals) and (vals % 5 == 0).mean() >= 0.9:
                _set(v, "discount_pct", f"values are round percentages ({', '.join(str(int(x)) for x in sorted(vals.unique())[:5])}...), not amounts", 0.75)
    # 3. market data: one row per date (or per date and symbol) with smooth price-like columns
    nums = [c for c in cols if c in nst and nst[c]]
    named_price = [c for c in nums if con(c) == "price_level"]
    tickers = [c for c in nums if TICKER_HEAD.match(str(c)) and con(c) in ("number", "margin_pct", "percent", "revenue", "money_other", "unit_price")]
    if p.time_col and (named_price or len(tickers) >= 2 or "trade_volume" in has or "ticker" in has):
        keys = [c for c in cols if con(c) == "ticker"]
        smooth = set(level_columns(df, keys, {c: cols[c]["concept"] for c in cols if c in df.columns})) if "_t" in df.columns else set()
        ref_med = float(np.median([nst[c]["med"] for c in named_price])) if named_price else None    # bands and moving averages sit on the price's scale
        for c in nums:
            if con(c) in ("price_level", "trade_volume", "ticker"):
                continue
            parts = re.split(r"[^A-Za-z]+", str(c))
            same_scale = bool(ref_med) and 0.5 <= (nst[c]["med"] / ref_med) <= 2 if nst.get(c) else False
            if c in smooth and (PRICE_PART.search(c) or c in tickers or any(TICKER_HEAD.match(x) for x in parts if x) or same_scale):
                _set(v := cols[c], "price_level", "moves smoothly from one date to the next, like a price (shown as levels, never added up)", 0.7)
            elif re.search(r"volume", str(c), re.I):
                _set(cols[c], "trade_volume", "traded volume")
    elif p.time_col and p.kind == "periodic":
        # one row per date, no names to go on: a smooth series is a level (balance, index, headcount), not a flow
        smooth = set(level_columns(df, [], {c: cols[c]["concept"] for c in cols if c in df.columns})) if "_t" in df.columns else set()
        for c in nums:
            if c in smooth and con(c) in ("number", "margin_pct", "percent", "money_other") and cols[c]["confidence"] < 0.6:
                _set(cols[c], "level_value", "moves smoothly from one date to the next: a level (like a balance), shown as latest/average, never added up", 0.6)
    # 4. dates that are mostly after the data ends describe the row (expiry, due date), they are not events
    for c, v in cols.items():
        if CONCEPTS[v["concept"]].kind != "date" or c == p.time_col or v["concept"] != "event_date" or c not in df.columns:
            continue
        d = pd.to_datetime(df[c], errors="coerce").dropna()
        end = df["_t"].max() if "_t" in df.columns and df["_t"].notna().any() else pd.Timestamp.now()
        if len(d) and (d > end).mean() > 0.5:
            if role.get("entity") == "product" or "product_id" in has:
                _set(v, "expiry_date", "mostly later than the data ends: looks like an expiry date", 0.6)
            else:
                _set(v, "due_date", "mostly later than the data ends: looks like a due date", 0.55)


def _context_rules(df, cols: dict, nst: dict, role: dict, fhint: dict) -> list[str]:
    """Settle words whose meaning depends on what the file is about. Returns plain notes for the reading page.
    - selling or buying: 'qty ordered' is units sold in a sales file but units ordered from suppliers in a purchase file;
      'party' is the customer in a sales register and the supplier in a purchase register;
    - a discount written as a share (0.05) is a discount %, not an amount;
    - an order file whose only money column is a generic 'value' or 'payment' column: that column is the sale."""
    notes = []
    has = {v["concept"] for v in cols.values()}
    tok = lambda c: set(tokens(c))
    purchase = fhint.get("purchase", 0) >= 0.6 or ("supplier_id" in has and "customer_id" not in has and has & {"units_ordered", "units_received", "unit_cost", "cost"} != set()) \
        or ("units_received" in has and "customer_id" not in has)
    selling = not purchase and (has & {"revenue", "profit", "customer_id", "gross_revenue"} != set()) and role.get("role") in ("transactions", "lines", "periodic")
    for c, v in cols.items():
        if v.get("source") in ("owner", "memory"):
            continue
        st = nst.get(c) or {}
        if selling and v["concept"] == "units_ordered" and "units_received" not in has:
            _set(v, "quantity", "in a sales file, the quantity a customer ordered is the units sold", 0.7)
        elif purchase and v["concept"] == "quantity" and tok(c) & {"ordered", "order", "po", "indent", "requested"}:
            _set(v, "units_ordered", "in a purchase file, the ordered quantity is units ordered from the supplier", 0.7)
        elif purchase and v["concept"] == "customer_id" and tok(c) & {"party", "debtor", "account"}:
            _set(v, "supplier_id", "in a purchase file, the party is the supplier", 0.7)
        if v["concept"] == "discount" and st and st.get("max", 9) <= 1 and st.get("min", -1) >= 0 and st.get("int", 1) < 0.98:
            _set(v, "discount_pct", f"values run from {st['min']:g} to {st['max']:g}: a share of the price (discount %), not an amount", 0.75)
    money_flows = [c for c, v in cols.items() if CONCEPTS[v["concept"]].money and CONCEPTS[v["concept"]].agg == "sum"]
    if fhint.get("transactions", 0) >= 0.6 and fhint.get("expense", 0) < 0.6 and len(money_flows) == 1 and cols[money_flows[0]]["concept"] == "revenue":
        _set(cols[money_flows[0]], "revenue", "the only amount in a table of sales / invoices / orders", 0.78)
    if fhint.get("expense", 0) >= 0.6:
        for c, v in cols.items():
            if v.get("source") == "auto" and v["concept"] in ("revenue", "money_other", "gross_revenue") and name_score(c, CONCEPTS["revenue"].synonyms)[0] < 0.9:
                _set(v, "expense", "an amount in an expenses table is money spent", 0.72)
                notes.append(f"'{c}' was read as money spent because this table is about expenses.")
    has = {v["concept"] for v in cols.values()}
    if role.get("role") in ("transactions", "lines") and "revenue" not in has and "gross_revenue" not in has:
        cand = [c for c, v in cols.items() if v["concept"] == "money_other" and nst.get(c) and nst[c]["neg"] <= 0.02 and v.get("source") == "auto"]
        if cand:
            best = max(cand, key=lambda c: nst[c]["med"])
            _set(cols[best], "revenue", "the only positive money column in a log of orders: read as the sale amount", 0.6)
            notes.append(f"'{best}' was read as the sale amount because the file has no other sales column.")
    return notes



UNIT_TOKENS = {"sec", "secs", "second", "seconds", "min", "mins", "minute", "minutes", "hr", "hrs", "hour", "hours", "day", "days", "week", "weeks", "month", "months"}
SHARE_TOKENS = {"pct", "percent", "percentage", "rate", "share", "ratio"}
MONEY_TOKENS = {"amount", "amt", "price", "cost", "value", "salary", "wage", "wages", "revenue", "sales", "spend", "fee", "fees", "budget", "income", "profit",
                "tax", "gst", "vat", "payment", "paid", "refund", "balance"} | {c.lower() for c in CURRENCIES}
ORDERISH = {"order", "orders", "invoice", "inv", "bill", "receipt", "txn", "transaction", "trx", "sale", "sales", "booking", "voucher", "po", "so"}
GENERIC_ID = {"id", "no", "number", "num", "ref", "code", "key"}


def _header_rules(df, cols: dict, nst: dict, cst: dict) -> None:
    """What a header says about units and scale outranks a loose name match:
    - 'lead_time_days', 'resolution_hours', 'avg_session_sec', 'credit_days': a time taken, in that unit (never money or a count);
    - 'bounce_rate', 'on_time_rate', 'gst_pct', 'mobile_share' holding 0..1 (or 0..100 for pct): a percentage, not a price or tax amount;
    - 'qty_on_order' / 'stock_value': units on order and the value of stock, not sales or units bought;
    - 'delay_reason' is a reason even when its values read like outcomes;
    - whole-number counts in a file with no products or prices (add_to_cart, checkout_started) are activity counts, not units sold."""
    has = {v["concept"] for v in cols.values()}
    commerce = bool(has & {"product_id", "unit_price", "unit_cost", "revenue", "gross_revenue", "cost"})
    for c, v in cols.items():
        if v.get("source") in ("owner", "memory"):
            continue
        t = set(tokens(c))
        st = nst.get(c)
        con = v["concept"]
        if st:
            last = tokens(c)[-1] if tokens(c) else ""
            unit_end = last in UNIT_TOKENS and not (t & {c.lower() for c in CURRENCIES})
            countish = t & {"per", "units", "qty", "quantity", "count", "visits", "orders", "sessions", "number"}
            if (unit_end or (t & UNIT_TOKENS and not (t & MONEY_TOKENS))) and not countish and con != "age" and st["neg"] <= 0.02 \
                    and not (con in ("duration", "promised_duration") and v["confidence"] >= 0.7):
                promised = bool(t & {"promised", "sla", "target", "expected", "planned", "estimated"})
                _set(v, "promised_duration" if promised else "duration", f"the header gives a time unit ({', '.join(sorted(t & UNIT_TOKENS))})", 0.78)
                continue
            if t & SHARE_TOKENS and st["min"] >= 0 and con not in ("discount_pct", "margin_pct", "rating"):
                fraction = st["max"] <= 1.0 and st["int"] < 0.98
                pct_scale = bool(t & {"pct", "percent", "percentage"}) and st["max"] <= 100
                if fraction or pct_scale:
                    cid = "discount_pct" if t & {"discount", "disc"} else "margin_pct" if t & {"margin", "markup"} else "percent"
                    _set(v, cid, "the header says it is a rate or share" + (" and the values run from 0 to 1" if fraction else " written in percent"), 0.78)
                    continue
            if con in ("units_ordered", "quantity", "stock_level") and "order" in t and t & {"on", "open", "pending", "transit"}:
                _set(v, "on_order", "units on order (waiting to arrive), a level, not units sold or bought", 0.78)
                continue
            if con in ("stock_level", "money_other", "revenue") and t & {"stock", "inventory"} and t & {"value", "amount", "worth", "valuation"}:
                _set(v, "stock_value", "the money value of stock held, a level that is not added up over time", 0.8)
                continue
            if con == "quantity" and not commerce and name_score(c, CONCEPTS["quantity"].synonyms)[0] < 0.6 and st["int"] >= 0.97:
                _set(v, "activity_count", "a count of actions in a file with no products or prices", 0.6)
                continue
            if con == "units_ordered" and not commerce and t <= {"orders", "order", "count", "number", "no", "of", "total"}:
                _set(v, "activity_count", "the number of orders (a count of actions), not units bought", 0.7)
                continue
        if CONCEPTS[con].kind == "key" and con not in ("order_id", "entity_id") and "name" in t:
            twin = [k for k, w in cols.items() if k != c and w["concept"] == con and "name" not in set(tokens(k)) and (id_header(k) or ID_HEAD.search(k))]
            if twin:
                _set(v, "name_label", f"the name that goes with '{twin[0]}' (the id column is the key)", 0.85)
                continue
        if con == "unit_price" and t & {"list", "mrp", "rrp", "msrp", "original", "catalogue", "catalog", "regular", "base", "standard", "tag"} \
                and any(w["concept"] == "unit_price" for k, w in cols.items() if k != c):
            _set(v, "list_price", "the price before discount; the table has a separate selling price", 0.85)
            continue
        if con == "name_label" and t & {"review", "comment", "feedback", "ticket", "complaint", "message", "subject", "remark", "remarks", "note", "notes"}:
            _set(v, "free_text", "a title or comment someone wrote, not the name of a thing", 0.75)
            continue
        if con == "segment" and t & {"type", "class", "kind", "tier", "category"} and not t & {"customer", "client", "member", "membership", "loyalty", "account", "user"} \
                and "customer_id" not in has:
            v.update(concept="group", label=CONCEPTS["group"].label, reasons=["a type or class of something other than customers"] + v["reasons"][:2])
            continue
        if con == "status" and t & {"reason", "cause", "why"}:
            _set(v, "reason", "the header names a reason", 0.75)
        money_in = has & {"product_id", "unit_price", "unit_cost", "quantity", "stock_level", "name_label", "revenue", "gross_revenue", "cost"}
        if con == "product_group" and (t & {"expense", "cost", "ticket", "issue", "complaint", "spend", "budget", "account", "ledger"}
                                       or (not money_in and not t & {"product", "item", "sku", "brand", "menu", "dish", "service", "cuisine", "department"})):
            v.update(concept="group", label=CONCEPTS["group"].label, reasons=["a category in a table with no products (expense or ticket type)"] + v["reasons"][:2])
    # two columns read as the order: the one whose header names the order keeps it, the other is another record's id
    oids = [c for c, v in cols.items() if v["concept"] == "order_id" and v.get("source") == "auto"]
    if len(oids) > 1:
        # the one that says 'order' is the order; otherwise the first (files lead with their own number: GRN No before the supplier's Invoice No)
        named = [c for c in oids if set(tokens(c)) & {"order", "orders"}] or oids[:1]
        if named:
            for c in oids:
                if c not in named:
                    cols[c].update(concept="entity_id", label=CONCEPTS["entity_id"].label,
                                   reasons=[f"this file's own record id; '{named[0]}' is the order"] + cols[c]["reasons"][:2])

# ---------------- main ----------------
def infer_table(p, memory: dict | None = None, owner: dict | None = None) -> dict:
    """Returns {"columns": {col: {...}}, "file": {...}, "identities": [...]}"""
    memory, owner = memory or {}, owner or {}
    df, roles = p.df, p.roles
    usable = {c: i for c, i in roles.items() if not c.startswith("__") and c not in ("_t", "_row") and i["role"] not in ("empty", "constant", "ignore")}
    for c, i in roles.items():                         # a reorder point or unit cost that is the same everywhere still means something
        if i["role"] == "constant":
            from ..understand.roles import clean_numeric
            num = df[c] if pd.api.types.is_numeric_dtype(df[c]) else clean_numeric(df[c])
            if num is not None and num.notna().mean() > 0.9 and \
                    max(name_score(c, CONCEPTS[k].synonyms)[0] for k in ("reorder_level", "unit_cost", "unit_price", "revenue", "cost", "expense", "quantity", "tax", "discount")) >= 0.8:
                usable[c] = {**i, "role": "measure"}
                if getattr(num, "attrs", {}).get("currency_symbol"):
                    roles[c]["currency_symbol"] = num.attrs["currency_symbol"]
    from ..understand.roles import clean_numeric as _cn
    def _num(s):
        if pd.api.types.is_numeric_dtype(s):
            return s
        v = _cn(s)
        return v if v is not None else pd.to_numeric(s, errors="coerce")
    nst = {c: num_stats(_num(df[c])) for c, i in usable.items() if i["role"] == "measure"}
    nst = {c: (v if v is not None or not usable[c].get("unique") == 1 else {"n": 1, "int": 1.0, "dec2": 0.0, "neg": 0.0, "zero": 0.0, "min": 0.0, "max": 0.0, "med": 0.0, "nu": 1}) for c, v in nst.items()}
    cst = {c: cat_stats(df[c]) for c, i in usable.items() if i["role"] != "measure"}
    ncache: dict = {}

    def nscore(col, cid):
        k = (col, cid)
        if k not in ncache:
            ncache[k] = name_score(col, CONCEPTS[cid].synonyms)[0] if CONCEPTS[cid].synonyms else 0.0
        return ncache[k]

    ids = find_identities(df, [c for c in nst if nst[c]])
    hints = identity_hints(ids, nst, nscore)
    fhint = file_name_hint(p.name)
    cols: dict[str, dict] = {}
    for c, info in usable.items():
        cands = candidates_for(info["role"], info, c)
        pii = is_pii(c)
        if pii and c in nst and nst[c] and nst[c]["max"] < 100000 and re.search(r"mobile|phone", c, re.I) and not re.search(r"e_?mail|address|birth|dob|ssn|aadhaar|passport", c, re.I):
            pii = False                                # 'mobile_share' = 0.66, 'phone_orders' = 12: numbers about phones, not phone numbers
        if pii and tokens(c) == ["name"] and c in cst and cst[c]["vals"]:
            # a column headed 'Name' that holds codes like '#1001' or 'SO-2231' is a document number, not a person's name
            coded = sum(1 for v in cst[c]["vals"][:40] if re.fullmatch(r"#\s*\d+|[A-Z]{1,5}[-/]?\d{3,}|\d{3,}", v.strip())) / max(1, min(40, len(cst[c]["vals"])))
            if coded >= 0.8:
                pii = False
        if pii:
            cands = [CONCEPTS["personal"]] + [x for x in cands if x.kind == "key"]
        scored = []
        for con in cands:
            ns, why_n = name_score(c, con.synonyms) if con.synonyms else (0.0, None)
            vs, why_v = value_score(con.id, nst.get(c), cst.get(c))
            if vs == 0.0 and con.id not in ("personal",):
                continue
            if con.id == "personal":
                vs = 0.9 if pii else 0.0
                if vs == 0:
                    continue
            s = W_NAME * ns + W_VALUE * vs
            if con.id in ("group", "number"):
                s = 0.3                                    # the neutral fallback
            elif con.id == "entity_id":
                s = vs * 0.75                              # a code column whose entity we cannot name yet
            elif con.id == "event_date" and ns < 0.3:
                s = 0.6
            elif con.id == "age" and ns < 0.3:
                s = 0.1                                    # 18..80 whole numbers are only an age if the header says so
            elif ns < 0.3:                                 # value evidence alone: weaker, unless very specific
                # values alone may suggest a meaning, but must not outvote a header that clearly names another one
                s = vs * 0.8 if vs >= 0.9 else (vs * 0.6 if vs >= 0.85 else (vs * 0.45 if vs >= 0.6 else 0.1))
            if con.kind == "key" and con.id != "entity_id" and not (ID_HEAD.search(c) or id_header(c)) and ns < 0.99 and not (vs >= 0.6 and ns >= 0.3):
                s *= 0.6                                   # a key needs an id-like header or a full name match
            if con.kind == "key" and LOCATION_TOKEN.search(c):
                s *= 0.5                                   # customer_city is a place, not a customer
            if con.id == "location" and LOCATION_TOKEN.search(c) and cst.get(c) and cst[c]["nu"] >= 2:
                s = max(s, 0.72)
            reasons = []
            if why_n and ns >= 0.3:
                reasons.append(f"header matches '{why_n}'")
            if why_v:
                reasons.append(why_v)
            b = hints.get(c, {}).get(con.id)
            if b:
                s += b[0]; reasons.append(b[1])
            if info.get("percent_text"):                   # written as '10%': a share, not an amount
                if con.id in ("discount_pct", "percent", "margin_pct"):
                    s += 0.35; reasons.append("written as percentages")
                elif con.money:
                    s *= 0.3
            scored.append((min(s, 1.0), con.id, reasons))
        if not scored:
            continue
        scored.sort(key=lambda x: -x[0])
        top = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        conf = round(max(0.05, min(1.0, top[0] * (0.75 + 0.25 * min(1.0, (top[0] - second) / 0.25)))), 2)
        cols[c] = {"concept": top[1], "label": CONCEPTS[top[1]].label, "confidence": conf, "reasons": top[2][:4],
                   "alternatives": [(cid, round(s, 2)) for s, cid, _ in scored[1:4]], "source": "auto"}
    _header_rules(df, cols, nst, cst)
    concept_of = {c: v["concept"] for c, v in cols.items()}
    role = file_role(p, concept_of, fhint)
    # structure evidence: in a stock snapshot, the running counts are levels, not flows (units sold per day stay a flow)
    levels = set(role.get("levels") or [])
    if role["role"] == "snapshot" or (role["role"] == "master" and fhint.get("snapshot", 0) >= 0.6):
        for c, v in cols.items():
            if role["role"] == "snapshot" and c not in levels:
                continue
            money_head = bool(set(tokens(c)) & MONEY_TOKENS)
            if v["concept"] in ("revenue", "money_other") and (money_head or name_score(c, STOCK_NAME)[0] < 0.6):
                continue                                  # an amount in a periodic file (expense, budget) is not a stock count
            if v["concept"] in ("quantity", "activity_count", "number", "points", "revenue", "money_other") and (nst.get(c) or {}).get("int", 0) >= 0.9:
                v.update(concept="stock_level", label=CONCEPTS["stock_level"].label, confidence=max(v["confidence"], 0.7),
                         reasons=[f"a count in a {role['role']} file is a level (stock on hand), not something to add up over time"] + v["reasons"][:2])
    _stock_and_market_rules(df, p, cols, nst, role, fhint)
    context_notes = _context_rules(df, cols, nst, role, fhint)
    for i in ids:
        if i["type"] in ("difference", "net"):
            sub = i["cols"][1]
            if sub in cols and cols[sub]["concept"] == "discount_pct" and cols[sub].get("source") == "auto":
                _set(cols[sub], "discount", f"{i['text']}: it is taken off an amount, so it is an amount too", 0.8)
    tc = getattr(p, "time_col", None)
    if tc in cols and (cols[tc]["concept"] in ("done_date", "due_date") or (cols[tc]["concept"] == "signup_date" and role["role"] in ("transactions", "lines"))) and not any(v["concept"] == "event_date" for k, v in cols.items() if k != tc):
        _set(cols[tc], "event_date", "the file's timeline: the date each row happened (e.g. the date goods were received)", 0.75)
    if role["role"] == "master" and role.get("entity") == "product":
        for c, v in cols.items():
            if v["concept"] == "cost":
                v.update(concept="unit_cost", label=CONCEPTS["unit_cost"].label, reasons=["a cost in a product list is the cost of one unit"] + v["reasons"][:2])
            elif v["concept"] in ("revenue", "gross_revenue") and nst.get(c):
                v.update(concept="unit_price", label=CONCEPTS["unit_price"].label, reasons=["an amount in a product list is the price of one unit"] + v["reasons"][:2])
    if role["role"] == "master" and role.get("key") in cols and role.get("entity"):
        ent_concept = {"customer": "customer_id", "product": "product_id", "supplier": "supplier_id", "employee": "employee_id", "site": "site_id"}.get(role["entity"])
        if ent_concept and cols[role["key"]]["concept"] != ent_concept:
            cols[role["key"]].update(concept=ent_concept, label=CONCEPTS[ent_concept].label, confidence=max(cols[role["key"]]["confidence"], 0.75),
                                     reasons=["the unique key of a master list of " + role["entity"] + "s"])
    # in a sales log with no product code, the item name is the product (e.g. 'Item Name' in a till export)
    if role["role"] in ("transactions", "lines") and not any(v["concept"] == "product_id" for v in cols.values()):
        for c, v in cols.items():
            if v["concept"] == "name_label" and re.search(r"(item|product|menu|dish|service|article|sku)", c, re.I) and 2 <= df[c].nunique() <= 5000:
                v.update(concept="product_id", label=CONCEPTS["product_id"].label, confidence=max(v["confidence"], 0.7),
                         reasons=["the item sold on each row (there is no separate product code)"] + v["reasons"][:2])
                break
    # unique id in a transaction log is the order / transaction
    if role["role"] == "transactions":
        for c, v in cols.items():
            named = nscore(c, v["concept"]) >= 0.8          # 'Customer ID', 'Account ID': the header already says what it is
            others = any(vv["concept"] == "order_id" for kk, vv in cols.items() if kk != c)    # a ticket_id next to an order_id is the ticket
            if CONCEPTS[v["concept"]].kind == "key" and df[c].nunique() >= 0.9 * df[c].notna().sum() and v["concept"] not in ("order_id",) and v["confidence"] < 0.8 and not named \
                    and not others:
                v.update(concept="order_id", label=CONCEPTS["order_id"].label, confidence=max(v["confidence"], 0.7), reasons=["unique per row in a transaction log"] + v["reasons"][:2])
    # a number that never changes within a customer (or product) describes that customer, e.g. lifetime value or age.
    # It must be averaged over customers, never added up across their orders.
    if role["role"] in ("transactions", "lines"):
        for key_concept, ent in (("customer_id", "customer"), ("product_id", "product")):
            kc = next((c for c, v in cols.items() if v["concept"] == key_concept), None)
            if not kc:
                continue
            g = df[[kc] + [c for c in cols if c in nst and nst[c]]].dropna(subset=[kc])
            multi = g[kc].map(g[kc].value_counts()) >= 2
            g = g[multi]
            if g[kc].nunique() < 20:
                continue
            nun = g.groupby(kc).nunique()
            for c in nun.columns:
                v = cols[c]
                if (nun[c] <= 1).mean() >= 0.95 and v["concept"] not in ("unit_price", "unit_cost"):
                    v["attribute_of"] = ent
                    if CONCEPTS[v["concept"]].agg == "sum":
                        v["reasons"] = [f"same value on every row of the same {ent}: a {ent} detail, averaged rather than added up"] + v["reasons"][:2]
    for c, i in roles.items():                     # a constant currency column still says which currency the money is in
        if i["role"] == "constant" and c not in cols:
            v = df[c].dropna().astype(str).str.strip().str.upper()
            if len(v) and v.iloc[0] in CURRENCIES:
                cols[c] = {"concept": "currency", "label": "Currency", "confidence": 0.95, "reasons": [f"every row is in {v.iloc[0]}"], "alternatives": [], "source": "auto", "constant": v.iloc[0]}
    for c in usable:                                   # what the owner chose before for a column with the same name
        cid = memory.get("_".join(tokens(c)))
        if cid in CONCEPTS and c in cols and cols[c]["concept"] != cid:
            prev = cols[c]
            cols[c] = {"concept": cid, "label": CONCEPTS[cid].label, "confidence": 0.95, "reasons": ["you chose this for a column with the same name before"],
                       "alternatives": [(prev["concept"], prev["confidence"])] + prev.get("alternatives", [])[:2], "source": "memory"}
        elif cid in CONCEPTS and c in cols:
            cols[c]["source"] = "memory"; cols[c]["confidence"] = max(cols[c]["confidence"], 0.95)
    if not any(v["concept"] == "currency" for v in cols.values()):
        sym = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
        found = [sym[i["currency_symbol"]] for c, i in roles.items() if i.get("currency_symbol") in sym and cols.get(c, {}).get("concept") in
                 ("revenue", "gross_revenue", "cost", "expense", "profit", "unit_price", "unit_cost", "discount", "tax", "money_other")]
        if not found:
            found = [t.upper() for c, v in cols.items() if CONCEPTS[v["concept"]].money for t in tokens(c) if t.upper() in CURRENCIES and t.upper() not in ("ALL",)]
        if found:
            code = max(set(found), key=found.count)
            cols["__currency__"] = {"concept": "currency", "label": "Currency", "confidence": 0.8, "reasons": [f"amounts are written in {code}"], "alternatives": [], "source": "auto", "constant": code}
    for c, cid in (owner or {}).items():
        if c in usable and cid in CONCEPTS:
            prev = cols.get(c, {})
            cols[c] = {"concept": cid, "label": CONCEPTS[cid].label, "confidence": 1.0, "reasons": ["you confirmed this"], "alternatives": prev.get("alternatives", []), "source": "owner"}
    _calibrate(cols, nst, cst)
    for c, v in cols.items():
        if c.startswith("__"):
            v["needs_confirmation"] = False
            continue
        close = _close_call(c, v, nst, cst)
        if close is None and v["concept"] == "revenue" and v["confidence"] < 0.85 and any(w["concept"] == "money_other" for k, w in cols.items() if k != c):
            close = "money_other"                       # two loosely named amounts: which one is the sale is the owner's call
        v["needs_confirmation"] = v["source"] == "auto" and v["concept"] not in ("number", "group", "personal", "free_text", "entity_id") and (
            v["confidence"] < 0.6 or v["concept"] == "money_other" or close is not None)
        if close and v["needs_confirmation"]:
            v["unsure_between"] = close
    return {"columns": cols, "file": role, "identities": ids, "notes": context_notes}


VALUE_CERTAIN = {"yes_no", "gender", "currency", "sentiment", "movement_type", "status", "channel", "payment_method", "rating", "age"}
MONEY_SUM = {c.id for c in NUMBER_CONCEPTS if c.agg == "sum"}


def _calibrate(cols: dict, nst: dict, cst: dict) -> None:
    """How sure we are should follow the evidence: a header that names the meaning, with values that fit it, is a confident
    read (ship_date -> completed date, budget_inr -> plan, Yes/No -> yes/no). Never lowers a confidence, never changes a meaning."""
    for c, v in cols.items():
        if c.startswith("__") or v.get("source") != "auto" or v["concept"] not in CONCEPTS:
            continue
        con = CONCEPTS[v["concept"]]
        ns = name_score(c, con.synonyms)[0] if con.synonyms else 0.0
        vs, _ = value_score(v["concept"], nst.get(c), cst.get(c))
        floor = None
        # numbers and keys must show values that fit; for groups, dates and text the values can only rule a meaning out
        if vs >= 0.4 or (con.kind in ("date", "text", "group") and vs > 0):
            floor = 0.92 if ns >= 0.9 else 0.84 if ns >= 0.75 else 0.74 if ns >= 0.6 else None
        if v["concept"] in VALUE_CERTAIN and vs >= 0.85:
            floor = max(floor or 0, 0.82)
        if floor and floor > v["confidence"]:
            v["confidence"] = round(floor, 2)
            why = "the header names it and the values fit" if ns >= 0.6 else "every value fits this meaning"
            if why not in v["reasons"]:
                v["reasons"] = [why] + v["reasons"][:3]


def _close_call(c: str, v: dict, nst: dict, cst: dict) -> str | None:
    """A runner-up that is about as likely AND would change how the column is added up (a sale vs a cost, a flow vs a level)."""
    alts = [(cid, sc) for cid, sc in (v.get("alternatives") or []) if cid in CONCEPTS and cid != v["concept"]]
    if not alts or v["confidence"] >= 0.85:
        return None
    cid, sc = alts[0]
    a, b = CONCEPTS[v["concept"]], CONCEPTS[cid]
    if sc < v["confidence"] - 0.08 or a.kind != b.kind:
        return None
    if a.kind == "number" and (a.money != b.money or a.agg != b.agg or (v["concept"] in MONEY_SUM and cid in MONEY_SUM and a.polarity != b.polarity)):
        return cid
    return None


def unify_links(models: dict[str, dict], links: list) -> None:
    """Both ends of a used link identify the same entity: give them the same key concept (the more confident one)."""
    for l in links:
        if not getattr(l, "use", False):
            continue
        a = models.get(l.child, {}).get("columns", {}).get(l.child_col)
        b = models.get(l.parent, {}).get("columns", {}).get(l.parent_col)
        if not a or not b:
            continue
        ka, kb = CONCEPTS[a["concept"]].kind == "key", CONCEPTS[b["concept"]].kind == "key"
        best = max([x for x, k in ((a, ka), (b, kb)) if k] or [a, b], key=lambda x: x["confidence"])
        pm = models[l.parent]["file"]
        if pm.get("role") == "master" and pm.get("entity"):
            ec = {"customer": "customer_id", "product": "product_id", "supplier": "supplier_id", "employee": "employee_id", "site": "site_id"}.get(pm["entity"])
            if ec:
                best = {"concept": ec, "confidence": max(a["confidence"], b["confidence"], 0.8)}
        for x in (a, b):
            if x.get("source") == "owner":
                continue
            if x["concept"] == best["concept"]:
                x["confidence"] = max(x["confidence"], best["confidence"], 0.85)
                x["needs_confirmation"] = False
                continue
            if x["concept"] != best["concept"]:
                x.update(concept=best["concept"], label=CONCEPTS[best["concept"]].label, confidence=max(x["confidence"], best["confidence"]),
                         reasons=[f"links {l.child}.{l.child_col} to {l.parent}.{l.parent_col}"] + x["reasons"][:2])
                x["needs_confirmation"] = False

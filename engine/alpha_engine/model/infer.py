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
                       PAYMENT_WORDS, GENDER_VALUES, CURRENCIES, REGION_WORDS, SENTIMENT_WORDS, YES_NO_VALUES, ID_HEAD, PERSON_NAME, ALWAYS_PII, ID_VALUE)

FEW_ENTITY_KEYS = {"site_id", "employee_id", "supplier_id"}
LOCATION_TOKEN = re.compile(r"(^|_|\s)(city|state|country|region|zone|district|province|postal|zip|pincode|pin_code|territory)($|_|\s|code)", re.I)     # entities that are often few (6 warehouses, 12 staff)


def is_pii(col: str) -> bool:
    return bool(PERSON_NAME.search(col) or ALWAYS_PII.search(col))
W_NAME, W_VALUE = 0.5, 0.5
SAMPLE = 4000


# ---------------- names ----------------
def tokens(name: str) -> list[str]:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(name))
    s = re.sub(r"[%#]", " pct ", s)
    return [t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if t]


def _eq(t: str, u: str) -> bool:
    """t = synonym token, u = header token. Allows abbreviations in the header (cust ~ customer, qty ~ quantity's own synonym),
    plurals (unit ~ units) and small typos, but not a synonym being a mere prefix of a longer header word (sales != salesperson)."""
    if t == u:
        return True
    if len(u) >= 3 and t.startswith(u) and len(u) >= 0.4 * len(t):
        return True
    if len(t) >= 4 and u.startswith(t) and len(u) - len(t) <= 2:
        return True
    return min(len(t), len(u)) >= 5 and SequenceMatcher(None, t, u).ratio() >= 0.84


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
        expl = sum(1 for u in nt if any(_eq(t, u) for t in st)) / len(nt)
        sc = cov * (0.3 + 0.7 * expl) * (1.0 if cov == 1 else 0.8)
        r = SequenceMatcher(None, whole, syn).ratio()
        if r > 0.86:
            sc = max(sc, r)
        if sc > best:
            best, why = sc, syn
    return min(best, 1.0), why


# ---------------- value evidence ----------------
def num_stats(s: pd.Series) -> dict | None:
    v = pd.to_numeric(s, errors="coerce").dropna()
    if len(v) < 5:
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
        if cid in ("revenue", "gross_revenue", "cost", "expense", "money_other", "unit_price", "unit_cost"):
            if not pos and cid != "money_other":
                return 0.15, "has negative values"
            sc = 0.45 + (0.3 if st["dec2"] >= 0.4 else 0.15 if st["med"] >= 20 else 0.0)
            return sc, "positive amounts" + (" with cents" if st["dec2"] >= 0.4 else "")
        if cid in ("discount", "tax"):
            return (0.55 if pos else 0.1), ("non-negative amounts, often zero" if st["zero"] > 0.2 else "non-negative amounts")
        if cid == "profit":
            return (0.75 if 0.005 < st["neg"] < 0.6 else 0.45), ("can be negative, like profit" if st["neg"] > 0.005 else "amounts")
        if cid == "quantity":
            if st["int"] < 0.97:
                return 0.05, "not whole numbers"
            return (0.75 if st["min"] >= 0 and st["med"] <= 1000 else 0.35), "small whole numbers"
        if cid in ("stock_level", "reorder_level"):
            return (0.55 if st["int"] >= 0.9 and st["neg"] <= 0.05 else 0.15), "whole non-negative counts"
        if cid == "margin_pct":
            if st["max"] > 1000 or st["int"] > 0.98:
                return 0.05, None
            in1, in100 = st["min"] >= -1.5 and st["max"] <= 1.5, st["min"] >= -150 and st["max"] <= 150
            return (0.7 if (in1 or in100) else 0.1), "a percentage range"
        if cid == "rating":
            if st["min"] < 0 or st["max"] > 10 or st["nu"] > 101:
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
            ok = st["min"] >= 0 and (st["max"] <= 1 or st["max"] <= 100) and st["int"] < 0.98
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
        if cs["nu"] >= 20 and coded >= 0.8:
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
        keyish = bool(ID_HEAD.search(col)) or len(tokens(col)) == 1
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
              "supplier": ("suppliers", "vendors"), "employee": ("employees", "staff", "agents"), "site": ("stores", "branches", "outlets", "warehouses", "sites")}


def file_name_hint(fname: str) -> dict[str, float]:
    base = re.sub(r"\.(csv|xlsx|xls)$", "", fname, flags=re.I)
    return {k: name_score(base, v)[0] for k, v in FILE_HINTS.items()}


def file_role(p, concept_of: dict[str, str], fhint: dict[str, float]) -> dict:
    df, n = p.df, len(p.df)
    keys = [c for c, k in concept_of.items() if CONCEPTS[k].kind == "key" and c in df.columns]
    if p.kind == "summary":
        return {"role": "summary", "entity": None, "reason": "a few summary rows"}
    if p.time_col is None:
        for c in keys:
            u = df[c].nunique(dropna=True)
            if u >= 0.98 * df[c].notna().sum() and u >= 5:
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
    for c in keys:
        if concept_of[c] == "order_id":
            continue
        g = df[[c]].assign(_d=t.dt.normalize()).dropna()
        if len(g) < 20:
            continue
        per = g.groupby(c)["_d"].nunique()
        nd = g["_d"].nunique()
        dup = g.duplicated().mean()
        coverage = g.groupby("_d")[c].nunique().mean() / max(len(per), 1)      # share of all items seen on a typical date
        if per.median() >= 3 and dup <= 0.05 and nd <= 0.5 * len(g) and len(per) >= 3 and coverage >= 0.5:
            score = 0.6 + 0.4 * fhint.get("snapshot", 0)
            if score >= 0.6:
                return {"role": "snapshot", "entity": CONCEPTS[concept_of[c]].entity, "key": c,
                        "reason": f"the same {c} appears once per date across {nd} dates (a stock or status snapshot)"}
    if p.kind == "periodic":
        return {"role": "periodic", "entity": None, "reason": "about one row per date (period totals)"}
    return {"role": "transactions", "entity": "order", "reason": "dated rows, one per event or line"}


# ---------------- main ----------------
def infer_table(p, memory: dict | None = None, owner: dict | None = None) -> dict:
    """Returns {"columns": {col: {...}}, "file": {...}, "identities": [...]}"""
    memory, owner = memory or {}, owner or {}
    df, roles = p.df, p.roles
    usable = {c: i for c, i in roles.items() if not c.startswith("__") and c not in ("_t", "_row") and i["role"] not in ("empty", "constant", "ignore")}
    nst = {c: num_stats(df[c]) for c, i in usable.items() if i["role"] == "measure"}
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
        if is_pii(c):
            cands = [CONCEPTS["personal"]] + [x for x in cands if x.kind == "key"]
        scored = []
        for con in cands:
            ns, why_n = name_score(c, con.synonyms) if con.synonyms else (0.0, None)
            vs, why_v = value_score(con.id, nst.get(c), cst.get(c))
            if vs == 0.0 and con.id not in ("personal",):
                continue
            if con.id == "personal":
                vs = 0.9 if is_pii(c) else 0.0
                if vs == 0:
                    continue
            s = W_NAME * ns + W_VALUE * vs
            if con.id in ("group", "number"):
                s = 0.3                                    # the neutral fallback
            elif con.id == "entity_id":
                s = vs * 0.75                              # a code column whose entity we cannot name yet
            elif con.id == "event_date" and ns < 0.3:
                s = 0.6
            elif ns < 0.3:                                 # value evidence alone: weaker, unless very specific
                s = vs * 0.8 if vs >= 0.85 else (vs * 0.45 if vs >= 0.6 else 0.1)
            if con.kind == "key" and con.id != "entity_id" and not ID_HEAD.search(c) and ns < 0.99 and not (vs >= 0.6 and ns >= 0.3):
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
            scored.append((min(s, 1.0), con.id, reasons))
        if not scored:
            continue
        scored.sort(key=lambda x: -x[0])
        top = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        conf = round(max(0.05, min(1.0, top[0] * (0.75 + 0.25 * min(1.0, (top[0] - second) / 0.25)))), 2)
        cols[c] = {"concept": top[1], "label": CONCEPTS[top[1]].label, "confidence": conf, "reasons": top[2][:4],
                   "alternatives": [(cid, round(s, 2)) for s, cid, _ in scored[1:4]], "source": "auto"}
    concept_of = {c: v["concept"] for c, v in cols.items()}
    role = file_role(p, concept_of, fhint)
    # structure evidence: in a stock snapshot, counts are levels, not flows
    if role["role"] == "snapshot" or (role["role"] == "master" and fhint.get("snapshot", 0) >= 0.6):
        for c, v in cols.items():
            if v["concept"] in ("quantity", "activity_count", "number", "points") and (nst.get(c) or {}).get("int", 0) >= 0.9:
                v.update(concept="stock_level", label=CONCEPTS["stock_level"].label, confidence=max(v["confidence"], 0.7),
                         reasons=[f"a count in a {role['role']} file is a level (stock on hand), not something to add up over time"] + v["reasons"][:2])
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
    # unique id in a transaction log is the order / transaction
    if role["role"] == "transactions":
        for c, v in cols.items():
            if CONCEPTS[v["concept"]].kind == "key" and df[c].nunique() >= 0.9 * df[c].notna().sum() and v["concept"] not in ("order_id",) and v["confidence"] < 0.8:
                v.update(concept="order_id", label=CONCEPTS["order_id"].label, reasons=["unique per row in a transaction log"] + v["reasons"][:2])
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
    for c, cid in (owner or {}).items():
        if c in usable and cid in CONCEPTS:
            prev = cols.get(c, {})
            cols[c] = {"concept": cid, "label": CONCEPTS[cid].label, "confidence": 1.0, "reasons": ["you confirmed this"], "alternatives": prev.get("alternatives", []), "source": "owner"}
    for v in cols.values():
        v["needs_confirmation"] = v["source"] == "auto" and (v["confidence"] < 0.55 or v["concept"] == "entity_id") and v["concept"] not in ("number", "group", "personal", "free_text")
    return {"columns": cols, "file": role, "identities": ids}


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
            if x["concept"] != best["concept"]:
                x.update(concept=best["concept"], label=CONCEPTS[best["concept"]].label, confidence=max(x["confidence"], best["confidence"]),
                         reasons=[f"links {l.child}.{l.child_col} to {l.parent}.{l.parent_col}"] + x["reasons"][:2])
                x["needs_confirmation"] = False

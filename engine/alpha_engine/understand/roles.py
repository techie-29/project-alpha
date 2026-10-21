"""Stage 1a: decide what every column IS (time, measure, category, flag, id, text ...).

Design rules (learned from real bugs):
  * Several kinds of evidence vote (header, value shape, spread of values). Values outweigh headers.
  * Every decision carries a confidence and plain-language reasons. Low confidence => owner confirms.
  * A column may have a main role plus secondary roles (a 1-5 rating is a measure AND can slice).
  * Hard safety rules run afterwards (enforce_rules) and can veto a decision.
  * The decision is made once, stored, and read by every later stage. Nothing re-guesses.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd

# ---------- header hints (weak evidence) ----------
STRONG_ID = re.compile(r"(zip|postal|pincode|pin_code|phone|mobile|uuid|guid|sku|barcode|ssn|aadhaar|passport)", re.I)
ID_TOKEN = re.compile(r"(^|[_\s\-])(id|code|no|num|number|key|ref|reference)($|[_\s\-])|[a-z]Id$", re.I)
MONEY = re.compile(r"(sales|revenue|amount|price|cost|profit|total|fee|tax|discount|value|salary|spend|income|expense|charge|payment|balance|fare)", re.I)
COUNT = re.compile(r"(qty|quantity|units|count|number_of|items|points|visits|orders|views|clicks|sessions|days)", re.I)
PCT = re.compile(r"(pct|percent|percentage|margin|rate|ratio|share)", re.I)
RATING = re.compile(r"(rating|score|stars|grade|rank)", re.I)
DATE_HEAD = re.compile(r"(date|timestamp|created|updated|datetime)", re.I)
PERIOD_PART = re.compile(r"^(year|month|week|quarter|day|hour|yr|mon|wk|qtr)$", re.I)
BOOL_HEAD = re.compile(r"^(is|has|was|did|can)[_\s]|flag|active|enabled", re.I)
PII_HEAD = re.compile(r"(name|email|mail|phone|mobile|address|street|ssn|aadhaar|passport|dob|birth|token|password|ip_?addr)", re.I)

DATE_SHAPE = re.compile(r"(?:\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})|(?:[A-Za-z]{3,9}\.? \d{1,2},? \d{4})|(?:\d{1,2} [A-Za-z]{3,9}\.? \d{4})")
TIME_OF_DAY = re.compile(r"^\s*\d{1,2}:\d{2}(:\d{2})?(\s?[APap][Mm])?\s*$")
ID_PATTERN = re.compile(r"^[A-Za-z]{1,8}[-_ ]?\d{3,}$")
CUR = re.compile(r"[\$€£₹¥,\s%]")
PLAUSIBLE = (pd.Timestamp("1990-01-01"), pd.Timestamp.now() + pd.DateOffset(years=1))


def _is_text(s: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def _is_dt(s: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(s)


# ---------- cleaning ----------
def clean_numeric(s: pd.Series) -> pd.Series | None:
    """'$1,234.50', '12%', '(500)' -> numbers, if almost every value allows it."""
    if not _is_text(s):
        return None
    t = s.dropna().astype(str)
    if t.empty:
        return None

    def conv(x: pd.Series) -> pd.Series:
        x = x.astype(str).str.strip()
        neg = x.str.match(r"^\(.*\)$") | x.str.startswith("-")
        core = x.str.replace(r"^\((.*)\)$", r"\1", regex=True).str.replace(CUR, "", regex=True).str.lstrip("-")
        v = pd.to_numeric(core, errors="coerce")
        return v.where(~neg, -v)

    if len(t) > 5000 and conv(t.sample(5000, random_state=0)).notna().mean() < 0.9:
        return None                                    # a sample already shows this is text: skip converting every row
    if conv(t).notna().mean() >= 0.95:
        out = pd.Series(np.nan, index=s.index)
        mask = s.notna()
        out[mask] = conv(s[mask])
        return out
    return None


def infer_date_order(sample: pd.Series) -> str:
    """'iso' | 'day-first' | 'month-first' | 'ambiguous->day-first' (the report states which was assumed)."""
    vals = sample.dropna().astype(str).head(5000)
    if vals.str.match(r"^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}").mean() > 0.9:
        return "iso"
    parts = vals.str.extract(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.]\d{2,4}").dropna().astype(int)
    if len(parts):
        if (parts[0] > 12).any():
            return "day-first"
        if (parts[1] > 12).any():
            return "month-first"
    return "ambiguous->day-first"


def parse_dates(s: pd.Series, order: str) -> pd.Series:
    if _is_dt(s):
        return s
    if order == "excel":
        return pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="D", origin="1899-12-30", errors="coerce")
    if order in ("unix_s", "unix_ms"):
        return pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="s" if order == "unix_s" else "ms", errors="coerce")
    return pd.to_datetime(s, errors="coerce", dayfirst=(order not in ("iso", "month-first")), format="mixed")


def _date_shaped(s: pd.Series) -> bool:
    if _is_dt(s):
        return True
    if not _is_text(s):
        return False
    v = s.dropna().astype(str).head(500)
    return len(v) > 0 and v.str.contains(DATE_SHAPE).mean() > 0.9


def _plausible(parsed: pd.Series) -> bool:
    p = parsed.dropna()
    return len(p) > 0 and PLAUSIBLE[0] <= p.min() and p.max() <= PLAUSIBLE[1]


# ---------- scoring ----------
def _bool_like(s: pd.Series) -> bool:
    if s.dtype == bool:
        return True
    u = set(s.dropna().astype(str).str.strip().str.lower().unique())
    return 0 < len(u) <= 2 and u <= {"true", "false", "yes", "no", "y", "n", "t", "f", "0", "1", "1.0", "0.0"}


def _pattern(v: str) -> str:
    return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", v))[:24]


def classify_column(name: str, s: pd.Series, n_rows: int) -> dict:
    nn = int(s.notna().sum())
    info: dict = {"role": "empty", "secondary": [], "confidence": 1.0, "reasons": [], "non_null": nn}
    if nn == 0:
        info["reasons"].append("No values.")
        return info
    nu = int(s.nunique(dropna=True))
    info["unique"] = nu
    if nu == 1 and nn > 1:
        if nn < 0.98 * n_rows:
            # one value on some rows, blank on the rest (e.g. return_status = "Returned"): the blank is the other answer
            info.update(role="flag", presence=True, confidence=0.8)
            info["reasons"].append(f"Filled on {nn / n_rows:.0%} of rows with one value; blank means 'no'.")
        else:
            info.update(role="constant")
            info["reasons"].append("Every value is the same.")
        return info

    reasons = info["reasons"]
    scores: dict[str, float] = {}

    # --- time of day (never a calendar date) ---
    if _is_text(s) and s.dropna().astype(str).head(500).str.match(TIME_OF_DAY).mean() > 0.9:
        info.update(role="time_of_day", confidence=0.95)
        reasons.append("Values look like clock times (hh:mm:ss), not calendar dates.")
        return info

    # --- calendar time ---
    if _date_shaped(s):
        order = infer_date_order(s) if _is_text(s) else "native"
        parsed = parse_dates(s, order)
        rate = float(parsed.notna().sum() / nn)
        if rate > 0.9 and _plausible(parsed):
            info.update(role="time", date_order=order, parse_rate=round(rate, 4), confidence=0.95)
            if order == "ambiguous->day-first":
                info["confidence"] = 0.6
                reasons.append("Day and month could be swapped; assumed day-first.")
            reasons.append(f"{rate:.0%} of values parse as dates ({order}).")
            return info
        if rate > 0.5:
            info.update(role="time", date_order=order, parse_rate=round(rate, 4), confidence=0.45)
            reasons.append(f"Only {rate:.0%} of values parse as dates; the rest need checking.")
            return info

    num = s if (pd.api.types.is_numeric_dtype(s) and s.dtype != bool) else clean_numeric(s)
    is_bool = _bool_like(s)

    # --- numeric-encoded dates (Excel serials / unix timestamps), only with a date-ish header ---
    if num is not None and DATE_HEAD.search(name) and (num.dropna() % 1 == 0).all():
        lo, hi = float(num.min()), float(num.max())
        for order, a, b in (("excel", 20000, 70000), ("unix_s", 3e8, 3e9), ("unix_ms", 3e11, 3e12)):
            if a <= lo and hi <= b and _plausible(parse_dates(num, order)):
                info.update(role="time", date_order=order, confidence=0.6)
                reasons.append(f"Numbers fit {order} dates and the header says date; please confirm.")
                return info

    if is_bool and nu <= 2:
        info.update(role="flag", confidence=0.9 if (s.dtype == bool or BOOL_HEAD.search(name)) else 0.65)
        reasons.append("Only two values (true/false style).")
        return info

    hint_id = bool(ID_TOKEN.search(name))
    strong_id = bool(STRONG_ID.search(name))

    if num is not None:
        ints = bool((num.dropna() % 1 == 0).all())
        ratio = nu / nn
        # id vs measure vs category votes
        sid = 0.0
        if strong_id:
            sid += 0.7; reasons.append("Header names a code/identifier (zip, phone, sku ...).")
        if hint_id and nu > 60:
            sid += 0.5; reasons.append("Header says id/code and there are many distinct values.")
        if ints and ratio >= 0.9 and nn > 50 and not (MONEY.search(name) or COUNT.search(name) or PCT.search(name)):
            sid += 0.35; reasons.append("Whole numbers that are almost all different.")
        smeas = 0.5
        if MONEY.search(name) or COUNT.search(name) or PCT.search(name) or RATING.search(name):
            smeas += 0.25; reasons.append("Header reads like an amount, count, rate or rating.")
        if not ints:
            smeas += 0.15; reasons.append("Has decimals.")
        if sid >= 0.5:
            smeas -= 0.4
        scat = 0.0
        if PERIOD_PART.match(name.strip()) and ints:
            scat = 0.85; reasons.append("Looks like a part of a date (month/year/week); will be combined into a date.")
            info["period_part"] = name.strip().lower()
        elif ints and nu <= 12:
            scat = 0.4 + (0.05 if RATING.search(name) else 0)
        scores = {"id": sid, "measure": smeas, "category": scat}
        info["cleaned_text_numbers"] = bool(_is_text(s))
    else:
        v = s.dropna().astype(str).str.strip()
        low_card = nu <= max(60, 0.002 * n_rows)
        mid_card = nu <= 500 and (nu <= 0.05 * nn or (nn <= 20000 and nu <= 0.15 * nn)) and not PII_HEAD.search(name)
        pat_id = bool(v.head(1000).str.match(ID_PATTERN).mean() > 0.9) and nu > 60
        sid = 0.0
        if strong_id:
            sid += 0.7; reasons.append("Header names a code/identifier.")
        if hint_id and nu > 60:
            sid += 0.5; reasons.append("Header says id/code and there are many distinct values.")
        if pat_id:
            sid += 0.45; reasons.append("Values follow an id pattern like ABC-000123.")
        if nu >= 0.5 * nn and v.str.len().median() <= 20 and not low_card:
            sid += 0.3
        scat = 0.8 if low_card else (0.5 if mid_card else 0.0)
        if low_card:
            reasons.append(f"Only {nu} distinct values.")
        stext = 0.0 if (low_card or mid_card) else 0.6
        if PII_HEAD.search(name):
            stext += 0.2; info["pii"] = True
        scores = {"id": sid, "category": scat, "text": stext}

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second_score
    conf = float(np.clip(0.35 + 1.5 * margin, 0, 1)) if best_score >= 0.5 else 0.3
    info.update(role=best, confidence=round(conf, 2))
    info["secondary"] = [k for k, v in ranked[1:] if v >= 0.4 and k in ("category", "measure")]
    if best == "id" and "category" in info["secondary"]:
        info["secondary"].remove("category")
    return info


def profile_columns(df: pd.DataFrame) -> dict[str, dict]:
    n = len(df)
    roles = {c: classify_column(c, df[c], n) for c in df.columns if c != "_row"}
    enforce_rules(df, roles)
    for info in roles.values():
        info["needs_confirmation"] = bool(info["confidence"] < 0.7 or info.get("vetoed"))
    return roles


# ---------- hard safety rules (veto the decision, never silently) ----------
def enforce_rules(df: pd.DataFrame, roles: dict[str, dict]) -> list[str]:
    log: list[str] = []
    n = len(df)
    for c, info in roles.items():
        role = info["role"]
        if role == "measure":
            s = df[c]
            num = s if pd.api.types.is_numeric_dtype(s) else clean_numeric(s)
            ints = num is not None and bool((num.dropna() % 1 == 0).all())
            if num is None or num.dropna().empty:
                info.update(role="text", vetoed="measure rule: no numbers", confidence=0.3)
            elif ints and num.nunique() >= 0.99 * num.notna().sum() and num.notna().sum() > 50 and not (MONEY.search(c) or COUNT.search(c)):
                info.update(role="id", vetoed="measure rule: all-different whole numbers look like ids", confidence=0.5)
                log.append(f"{c}: measure -> id (all-different whole numbers).")
            elif ID_TOKEN.search(c) and STRONG_ID.search(c):
                info.update(role="id", vetoed="measure rule: header is a code", confidence=0.5)
                log.append(f"{c}: measure -> id (code header).")
        elif role == "time":
            order = info.get("date_order", "native")
            parsed = parse_dates(df[c], order) if order != "native" else df[c]
            if not _plausible(parsed):
                info.update(role="text", vetoed="time rule: dates outside 1990..next year", confidence=0.3)
                log.append(f"{c}: time -> text (implausible date range).")
    return log


def apply_owner_confirmations(roles: dict[str, dict], confirmed: dict[str, str]) -> dict[str, dict]:
    """The owner's choice always wins and is final (confidence 1)."""
    allowed = {"time", "measure", "category", "flag", "id", "text", "time_of_day", "ignore"}
    for col, role in confirmed.items():
        if col in roles and role in allowed:
            roles[col].update(role=role, confidence=1.0, source="owner", needs_confirmation=False)
            roles[col].pop("vetoed", None)
    return roles

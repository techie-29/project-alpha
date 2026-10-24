"""Reading dates the way a person would.

A date column in a real export can mix several ways of writing a date (03/04/2024, 2024-04-05, 5-Apr-24, 45387 as an
Excel day number, 20240405, 2024-04-05T10:15:00+05:30 ...). Each value is sorted by its shape, every shape is read
with its own exact rule, and the results are put back together. Day-first vs month-first is decided per column from
evidence (a day above 12, the other shapes in the same column, how smoothly the dates run in row order, sibling
columns, the currency of the file), and the report says which evidence decided it.

Also here:
  * period values and headers: 'Apr-2024', '2024-04', 'Q1 2024', '2024-W03', 'FY 2024-25' (start of the period)
  * wide tables whose column headers are periods ('Apr-2024', 'May-2024', ...) are turned into rows.
"""
from __future__ import annotations
import datetime as _dt
import re
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
          "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
          "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
JUNK = {"", "n/a", "na", "nan", "nat", "none", "null", "-", "--", "?", "tbd", "pending", "unknown", "not set",
        "0", "00/00/0000", "0000-00-00", "00-00-0000", "#n/a", "#value!", "nil"}

DATE_HEAD = re.compile(r"(date|\bdt\b|_dt$|^dt_|timestamp|datetime|created|updated|modified|posted|_at$|\bon$|_on$|\bday\b|"
                       r"\bwhen\b|period|month|\bweek|quarter|expir|\bexp\b|\bdue\b|deadline|\bdob\b|birth|joined|since|"
                       r"fecha|datum|\bdata\b|tarikh|tanggal|\btime\b)", re.I)

_TIME = r"(?:[\sT]+(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?(?:[.,]\d+)?\s*(am|pm)?)?"
RX = {
    "ymd": re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})" + _TIME + r"$"),
    "dmy": re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})" + _TIME + r"$"),
    "compact": re.compile(r"^((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:[\sT]?(\d{2})(\d{2})(\d{2})?)?$"),
    "named": re.compile(r"\b(" + _MON + r")\b"),
    "ym": re.compile(r"^((?:19|20)\d{2})[-/.](0?[1-9]|1[0-2])$"),
    "my": re.compile(r"^(0?[1-9]|1[0-2])[-/.]((?:19|20)\d{2})$"),
    "my_named": re.compile(r"^(" + _MON + r")[\s\-'./,]*(\d{4}|\d{2})$"),
    "ym_named": re.compile(r"^(\d{4})[\s\-'./,]*(" + _MON + r")$"),
    "quarter": re.compile(r"^(?:q([1-4])[\s\-'./]*(\d{4}|\d{2})|(\d{4})[\s\-./]*q([1-4]))$"),
    "week": re.compile(r"^(\d{4})[\s\-]*w(?:eek)?[\s\-]*(\d{1,2})$"),
    "fy": re.compile(r"^fy[\s\-']*(\d{2,4})(?:[\-/](\d{2,4}))?$"),
    "serial": re.compile(r"^\d{5}(?:\.\d+)?$"),
    "unix": re.compile(r"^\d{10}(?:\d{3})?$"),
}
_WEEKDAY = re.compile(r"^(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\.?,?\s+", re.I)
_ORDINAL = re.compile(r"(\d)(st|nd|rd|th)\b", re.I)
_TZ = re.compile(r"(\d{1,2}[:.]\d{2}(?:[:.]\d{2}(?:[.,]\d+)?)?(?:\s*[ap]m)?)\s*(?:z|utc|gmt|ist|[+-]\d{2}:?\d{2})$", re.I)
PERIOD_SHAPES = ("ym", "my", "my_named", "ym_named", "quarter", "week", "fy")
GRAIN = {"ym": "month", "my": "month", "my_named": "month", "ym_named": "month", "quarter": "quarter", "week": "week",
         "fy": "year", "year": "year"}


@dataclass
class DateRead:
    parsed: pd.Series                     # datetime64[ns], naive (wall-clock time as written)
    order: str                            # iso | day-first | month-first | mixed | excel | unix | native | period
    certain: bool                         # False when day/month order was a judgement call
    rate: float                           # share of non-blank values that became dates
    shapes: dict = field(default_factory=dict)
    grain: str = "day"                    # datetime | day | week | month | quarter | year
    reason: str = ""
    example: str = ""
    junk: int = 0


def _norm(v: str) -> str:
    t = str(v).strip().lower().replace(",", " ")
    t = _WEEKDAY.sub("", t)
    t = _ORDINAL.sub(r"\1", t)
    t = _TZ.sub(r"\1", t)
    t = re.sub(r"(\d{4}-\d{1,2}-\d{1,2})t(\d)", r"\1 \2", t)
    return re.sub(r"\s+", " ", t).strip()


def shape_of(t: str) -> str | None:
    for k in ("ymd", "dmy", "compact", "ym", "my", "my_named", "ym_named", "quarter", "week", "fy", "serial", "unix"):
        if RX[k].match(t):
            return k
    if RX["named"].search(t) and re.search(r"\d", t):
        return "named"
    return None


def _year(y: pd.Series) -> pd.Series:
    y = pd.to_numeric(y, errors="coerce")
    pivot = (_dt.date.today().year % 100) + 10
    return y.where(y >= 100, np.where(y <= pivot, 2000 + y, 1900 + y))


def _assemble(y, m, d, hh=None, mm=None, ss=None, ap=None) -> pd.Series:
    f = pd.DataFrame({"year": _year(y), "month": pd.to_numeric(m, errors="coerce"), "day": pd.to_numeric(d, errors="coerce")})
    ok = f["month"].between(1, 12) & f["day"].between(1, 31) & f["year"].between(1800, 2200)
    out = pd.Series(pd.NaT, index=f.index, dtype="datetime64[ns]")
    if ok.any():
        out[ok] = pd.to_datetime(f[ok], errors="coerce")
    if hh is not None:
        h = pd.to_numeric(hh, errors="coerce").fillna(0)
        if ap is not None:
            a = pd.Series(ap, index=f.index).fillna("")
            h = np.where((a == "pm") & (h < 12), h + 12, np.where((a == "am") & (h == 12), 0, h))
        delta = pd.to_timedelta(pd.Series(h, index=f.index), unit="h") + pd.to_timedelta(pd.to_numeric(mm, errors="coerce").fillna(0), unit="m") \
            + pd.to_timedelta(pd.to_numeric(ss, errors="coerce").fillna(0), unit="s")
        out = out + delta.where(pd.Series(h, index=f.index) < 24)
    return out


def _parse_shape(kind: str, u: pd.Series, dayfirst: bool | None = True) -> pd.Series:
    """u: normalised unique strings of one shape -> timestamps (same index)."""
    if kind == "ymd":
        g = u.str.extract(RX["ymd"])
        return _assemble(g[0], g[1], g[2], g[3], g[4], g[5], g[6])
    if kind == "dmy":
        g = u.str.extract(RX["dmy"])
        a, b = (g[0], g[1]) if dayfirst else (g[1], g[0])
        return _assemble(g[2], b, a, g[3], g[4], g[5], g[6])
    if kind == "compact":
        g = u.str.extract(RX["compact"])
        return _assemble(g[0], g[1], g[2], g[3], g[4], g[5])
    if kind in ("ym", "my"):
        g = u.str.extract(RX[kind])
        y, m = (g[0], g[1]) if kind == "ym" else (g[1], g[0])
        return _assemble(y, m, pd.Series(1, index=u.index))
    if kind in ("my_named", "ym_named"):
        g = u.str.extract(RX[kind])
        mon, y = (g[0], g[1]) if kind == "my_named" else (g[1], g[0])
        return _assemble(y, mon.map(MONTHS), pd.Series(1, index=u.index))
    if kind == "quarter":
        g = u.str.extract(RX["quarter"])
        q = pd.to_numeric(g[0].fillna(g[3]), errors="coerce")
        y = g[1].fillna(g[2])
        return _assemble(y, (q - 1) * 3 + 1, pd.Series(1, index=u.index))
    if kind == "week":
        g = u.str.extract(RX["week"])
        s = g[0] + "-W" + g[1].str.zfill(2) + "-1"
        return pd.to_datetime(s, format="%G-W%V-%u", errors="coerce")
    if kind == "fy":                                   # FY 2024-25 / FY24: Indian/UK style, starts 1 April of the first year
        g = u.str.extract(RX["fy"])
        y1 = _year(g[0])
        y1 = np.where(g[1].isna() & (g[0].str.len() <= 2), y1 - 1, y1)       # 'FY24' ends in 2024 -> starts April 2023
        return _assemble(pd.Series(y1, index=u.index), pd.Series(4, index=u.index), pd.Series(1, index=u.index))
    if kind == "serial":
        x = pd.to_numeric(u, errors="coerce")
        x = x.where(x.between(10000, 80000))
        return pd.to_datetime(x, unit="D", origin="1899-12-30", errors="coerce").dt.round("s")
    if kind == "unix":
        x = pd.to_numeric(u, errors="coerce")
        unit = np.where(u.str.len() >= 13, "ms", "s")
        out = pd.Series(pd.NaT, index=u.index, dtype="datetime64[ns]")
        for un in ("s", "ms"):
            m = unit == un
            if m.any():
                out[m] = pd.to_datetime(x[m], unit=un, errors="coerce")
        return out
    if kind == "named":
        out = pd.to_datetime(u, errors="coerce", format="mixed", dayfirst=bool(dayfirst))
        return out
    return pd.Series(pd.NaT, index=u.index, dtype="datetime64[ns]")


def _smooth(dates: pd.Series) -> float:
    """Typical jump between consecutive rows, in days (small = dates run smoothly in row order)."""
    d = dates.dropna()
    if len(d) < 3:
        return np.inf
    return float(np.median(np.abs(np.diff(d.values.astype("datetime64[D]").astype(np.int64)))))


def _in_order(dates: pd.Series) -> bool:
    """Rows are (mostly) in date order, so how smoothly they run is real evidence."""
    d = dates.dropna().values.astype("datetime64[D]").astype(np.int64)
    if len(d) < 5:
        return False
    st = np.diff(d)
    return bool((st >= 0).mean() >= 0.9 or (st <= 0).mean() >= 0.9)


def _regularity(dates: pd.Series) -> float:
    """How evenly the distinct dates are spaced (0 = perfectly regular). Used when row order says nothing."""
    u = np.sort(dates.dropna().unique())
    if len(u) < 4:
        return np.inf
    gaps = np.diff(u.astype("datetime64[D]").astype(np.int64)).astype(float)
    return float(np.std(gaps) / max(np.mean(gaps), 1e-9))


def _dmy_order(raw: pd.Series, norm: pd.Series, shapes: pd.Series, others: pd.Series, prefer: str | None) -> tuple[bool, bool, str]:
    """-> (dayfirst, certain, reason) for the d/m/y values of one column."""
    m = norm[shapes == "dmy"]
    g = m.str.extract(RX["dmy"])
    a, b = pd.to_numeric(g[0], errors="coerce"), pd.to_numeric(g[1], errors="coerce")
    a13, b13 = int((a > 12).sum()), int((b > 12).sum())
    if a13 and not b13:
        return True, True, f"{a13:,} value(s) have a first number above 12 (e.g. {raw[m.index[(a > 12).values][0]]}), so the day comes first"
    if b13 and not a13:
        return False, True, f"{b13:,} value(s) have a second number above 12 (e.g. {raw[m.index[(b > 12).values][0]]}), so the month comes first"
    if a13 and b13:
        first = a13 >= b13
        return first, False, f"day and month order is mixed inside this column ({a13:,} look day-first, {b13:,} month-first); read as {'day' if first else 'month'}-first"
    # no number above 12 anywhere: weigh other evidence
    df_c = _parse_shape("dmy", m, True)
    mf_c = _parse_shape("dmy", m, False)
    if others.notna().sum() >= 5:                      # other shapes in the same column are unambiguous: be consistent with them
        pos = pd.Series(np.arange(len(norm)), index=norm.index)
        ref = others.dropna()
        rp = pos[ref.index].values
        idx = np.clip(np.searchsorted(rp, pos[m.index].values), 0, len(rp) - 1)
        near = pd.Series(ref.values[idx], index=m.index)
        e1 = float(np.nanmedian(np.abs((df_c - near).dt.days)))
        e2 = float(np.nanmedian(np.abs((mf_c - near).dt.days)))
        if min(e1, e2) < 0.6 * max(e1, e2):
            return e1 <= e2, True, "matches the other date styles in the same column (nearby rows)"
    for cand, first in ((df_c, True), (mf_c, False)):          # monthly figures dated on the 1st: 01/04, 01/05, 01/06 ...
        d = cand.dropna()
        if len(d) >= 3 and (d.dt.day == 1).all() and d.dt.to_period("M").nunique() >= 3:
            return first, False, "every date falls on the 1st of a month when read this way (monthly figures)"
    s1, s2 = _smooth(df_c), _smooth(mf_c)
    if np.isfinite(min(s1, s2)) and min(s1, s2) < 0.6 * max(s1, s2) and _in_order(df_c if s1 <= s2 else mf_c):
        return s1 <= s2, True, "dates run in order down the file only when read this way"
    r1, r2 = _regularity(df_c), _regularity(mf_c)
    if np.isfinite(min(r1, r2)) and min(r1, r2) < 0.6 * max(r1, r2):
        return r1 <= r2, False, "dates are evenly spaced only when read this way"
    if prefer in ("day-first", "month-first"):
        return prefer == "day-first", False, f"no day above 12; followed {prefer} used elsewhere in your files"
    return True, False, "no day above 12 anywhere, so it could be either; assumed day-first"


def looks_like_dates(s: pd.Series, name: str = "") -> bool:
    """Cheap first look on a sample: is this column worth reading as dates?"""
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    v = s.dropna()
    if v.empty:
        return False
    v = v.sample(min(len(v), 400), random_state=0) if len(v) > 400 else v
    if pd.api.types.is_bool_dtype(v):
        return False
    if pd.api.types.is_numeric_dtype(v):
        if not DATE_HEAD.search(name) or not (v % 1 == 0).all():
            return bool(DATE_HEAD.search(name)) and bool(v.between(10000, 80000).mean() > 0.9)
        t = v.astype("int64").astype(str)
    else:
        t = v.map(lambda x: x.isoformat() if isinstance(x, (_dt.date, _dt.datetime)) else str(x))
    if isinstance(v.iloc[0], (_dt.date, _dt.datetime, pd.Timestamp)):
        return True
    n = t.map(_norn_safe)
    sh = n.map(shape_of)
    strong = sh.isin(["ymd", "dmy", "named"] + list(PERIOD_SHAPES)).mean()
    weak = sh.isin(["compact", "serial", "unix"]).mean()
    if strong >= 0.5:
        return True
    return bool(DATE_HEAD.search(name)) and (strong + weak) >= 0.8


def _norn_safe(x) -> str:
    try:
        return _norm(x)
    except Exception:
        return ""


def read_dates(s: pd.Series, name: str = "", prefer: str | None = None, force: bool = False, order: str | None = None) -> DateRead | None:
    """Read a column as dates. None when it does not look like a date column (unless force).
    order: 'day-first' / 'month-first' chosen by the owner (wins over every other clue)."""
    want = order
    if pd.api.types.is_datetime64_any_dtype(s):
        p = s.dt.tz_localize(None) if getattr(s.dt, "tz", None) is not None else s
        p = p.astype("datetime64[ns]")
        return DateRead(p, "native", True, 1.0 if s.notna().any() else 0.0, {"native": int(s.notna().sum())},
                        _grain(p), "stored as dates in the file", _example(s, p))
    if not force and not looks_like_dates(s, name):
        return None
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    nn = s.notna()
    # real date objects (Excel cells) first
    is_obj = nn & s.map(lambda x: isinstance(x, (_dt.date, _dt.datetime, pd.Timestamp)))
    if is_obj.any():
        out[is_obj] = pd.to_datetime(s[is_obj].map(lambda x: pd.Timestamp(x).tz_localize(None) if getattr(x, "tzinfo", None) else pd.Timestamp(x)), errors="coerce")
    rest = s[nn & ~is_obj]
    if pd.api.types.is_numeric_dtype(rest) or rest.map(lambda x: isinstance(x, (int, float, np.integer, np.floating))).all():
        txt = rest.map(lambda x: str(int(x)) if isinstance(x, (float, np.floating)) and float(x).is_integer() else str(x))
    else:
        txt = rest.map(lambda x: str(int(x)) if isinstance(x, (float, np.floating)) and float(x).is_integer() else str(x))
    uniq = pd.Series(txt.unique())
    un = uniq.map(_norn_safe)
    junk_u = un.isin(JUNK)
    shp = un.map(lambda t: None if t in JUNK else shape_of(t))
    # bare numbers are only dates when the header or the rest of the column says so
    numeric_shapes = shp.isin(["serial", "unix", "compact"])
    textual = shp.isin(["ymd", "dmy", "named"] + list(PERIOD_SHAPES)).sum()
    if numeric_shapes.any() and not (DATE_HEAD.search(name) or textual >= numeric_shapes.sum() or force):
        shp = shp.where(~numeric_shapes, None)
    parsed_u = pd.Series(pd.NaT, index=uniq.index, dtype="datetime64[ns]")
    for k in [k for k in shp.dropna().unique() if k != "dmy"]:
        m = shp == k
        parsed_u[m] = _parse_shape(k, un[m], True).values
    order, certain, reason = "iso", True, ""
    if (shp == "dmy").any():
        # put the unique-value results back on the rows, to judge day/month order in row context
        row_norm = txt.map(dict(zip(uniq, un)))
        row_shape = txt.map(dict(zip(uniq, shp)))
        others = txt.map(dict(zip(uniq, parsed_u)))
        others = pd.to_datetime(others.where(row_shape != "dmy"), errors="coerce")
        if want in ("day-first", "month-first"):
            dayfirst, certain, reason = want == "day-first", True, f"you chose {want}"
        else:
            dayfirst, certain, reason = _dmy_order(rest, row_norm, row_shape, others, prefer)
        m = shp == "dmy"
        parsed_u[m] = _parse_shape("dmy", un[m], dayfirst).values
        order = "day-first" if dayfirst else "month-first"
    kinds = shp.dropna().value_counts()
    if order == "iso" and len(kinds):
        top = kinds.index[0]
        order = {"serial": "excel", "unix": "unix", "named": "written month", "compact": "yyyymmdd"}.get(top, "period" if top in PERIOD_SHAPES else "iso")
    if len(kinds) > 1:
        order = order if order in ("day-first", "month-first") else "mixed"
    mp = dict(zip(uniq, parsed_u))
    out[rest.index] = pd.to_datetime(txt.map(mp), errors="coerce")
    junk_rows = int(txt.map(dict(zip(uniq, junk_u))).sum())
    good = int(out.notna().sum())
    denom = max(int(nn.sum()) - junk_rows, 1)
    shapes = {str(k): int(v) for k, v in txt.map(dict(zip(uniq, shp))).value_counts().items()}
    if is_obj.any():
        shapes["excel date"] = int(is_obj.sum())
    if not reason:
        reason = _shape_text(shapes)
    elif len(shapes) > 1:
        reason = _shape_text(shapes) + "; " + reason
    rd = DateRead(out, order, certain, good / denom, shapes, _grain(out, kinds), reason, _example(s, out), junk_rows)
    return rd


SHAPE_WORDS = {"ymd": "year-month-day", "dmy": "dd/mm/yyyy style", "named": "written month (5-Apr-24)", "compact": "yyyymmdd",
               "serial": "Excel day numbers", "unix": "Unix timestamps", "ym": "year-month", "my": "month/year", "my_named": "month name + year",
               "ym_named": "year + month name", "quarter": "quarters", "week": "ISO weeks", "fy": "financial years", "excel date": "Excel dates"}


def _shape_text(shapes: dict) -> str:
    parts = [f"{SHAPE_WORDS.get(k, k)} ({v:,})" for k, v in sorted(shapes.items(), key=lambda kv: -kv[1]) if k != "None"]
    if not parts:
        return ""
    return ("Written " + parts[0]) if len(parts) == 1 else ("Mixed styles: " + ", ".join(parts[:5]))


def _grain(p: pd.Series, kinds: pd.Series | None = None) -> str:
    d = p.dropna()
    if d.empty:
        return "day"
    if kinds is not None and len(kinds) and kinds.index[0] in GRAIN and kinds.iloc[0] >= 0.9 * kinds.sum():
        return GRAIN[kinds.index[0]]
    if (d != d.dt.normalize()).mean() > 0.05:
        return "datetime"
    if (d.dt.day == 1).all() and d.nunique() >= 2:
        return "quarter" if d.dt.month.isin([1, 4, 7, 10]).all() and d.dt.month.nunique() > 1 and len(d) >= 4 and _step(d) >= 85 else "month"
    return "day"


def _step(d: pd.Series) -> float:
    u = np.sort(d.unique())
    return float(np.median(np.diff(u).astype("timedelta64[D]").astype(int))) if len(u) > 1 else 0.0


def _example(raw: pd.Series, parsed: pd.Series) -> str:
    ok = parsed.dropna()
    if ok.empty:
        return ""
    i = ok.index[len(ok) // 2]
    v = raw[i]
    p = parsed[i]
    if isinstance(v, (_dt.date, _dt.datetime, pd.Timestamp)):
        v = pd.Timestamp(v).strftime("%Y-%m-%d %H:%M" if pd.Timestamp(v) != pd.Timestamp(v).normalize() else "%Y-%m-%d")
    shown = p.strftime("%d %b %Y %H:%M") if (p != p.normalize()) else p.strftime("%d %b %Y")
    return f"{v} -> {shown}"


# ---------- period headers: wide tables ('Apr-2024', 'May-2024' ... as columns) ----------
def header_period(h) -> tuple[pd.Timestamp, str] | None:
    if isinstance(h, (_dt.date, _dt.datetime, pd.Timestamp)):
        return pd.Timestamp(h), "day"
    t = _norn_safe(h)
    k = shape_of(t)
    if k is None and re.fullmatch(r"(19|20)\d{2}", t):
        k = "year"
    if k not in ("ymd", "dmy", "named", "year") + PERIOD_SHAPES:
        return None
    if k == "year":
        return pd.Timestamp(int(t), 1, 1), "year"
    v = _parse_shape(k, pd.Series([t]), True).iloc[0]
    if pd.isna(v):
        return None
    return pd.Timestamp(v), GRAIN.get(k, "day")


VALUE_NAME_DROP = re.compile(r"\b(monthly|weekly|daily|quarterly|yearly|annual|report|wide|data|sheet|export|final|v\d+|copy|by month|per month)\b", re.I)


def unpivot_periods(df: pd.DataFrame, file_name: str = "") -> tuple[pd.DataFrame, str | None]:
    """Columns named like periods hold one measure per period: turn them into rows (period, value)."""
    hits = {c: header_period(c) for c in df.columns if c != "_row"}
    per = {c: v for c, v in hits.items() if v is not None}
    if len(per) < 3:
        return df, None
    grains = pd.Series([g for _, g in per.values()]).value_counts()
    grain = grains.index[0]
    cols = [c for c, (_, g) in per.items() if g == grain]
    if len(cols) < 3:
        return df, None
    num_ok = [c for c in cols if pd.to_numeric(df[c].astype(str).str.replace(r"[,\s₹$€£%]", "", regex=True), errors="coerce").notna().mean()
              >= 0.8 * max(df[c].notna().mean(), 1e-9)]
    if len(num_ok) < 3 or len(num_ok) < 0.5 * len([c for c in df.columns if c != "_row"]) - 3:
        return df, None
    ids = [c for c in df.columns if c not in num_ok]
    base = re.sub(r"\.(csv|xlsx|xls|tsv|txt)$", "", file_name, flags=re.I)
    vname = VALUE_NAME_DROP.sub(" ", re.sub(r"[_\-]+", " ", base)).strip()
    vname = re.sub(r"\s+", " ", vname) or "Value"
    if vname.lower() in {c.lower() for c in ids}:
        vname = vname + " value"
    pname = {"month": "Month", "quarter": "Quarter", "week": "Week", "year": "Year"}.get(grain, "Date")
    long = df.melt(id_vars=ids, value_vars=num_ok, var_name="__period_header__", value_name=vname)
    long[pname if pname not in ids else pname + " (from headers)"] = long["__period_header__"].map({c: per[c][0] for c in num_ok}).astype("datetime64[ns]")
    long = long.drop(columns="__period_header__")
    if "_row" in long.columns:
        long["_row"] = np.arange(1, len(long) + 1)
    order = sorted(per[c][0] for c in num_ok)
    note = (f"The columns {num_ok[0]} ... {num_ok[-1]} are {len(num_ok)} {grain}s side by side; turned them into rows "
            f"({pname}, {vname}) so they can be charted over time ({order[0]:%b %Y} to {order[-1]:%b %Y}).")
    return long, note


NOT_TICKERS = {"ID", "QTY", "MRP", "GST", "VAT", "SKU", "UOM", "TAX", "AMT", "NO", "SNO", "SR", "PO", "CGST", "SGST", "IGST", "HSN", "EAN", "UPC", "TOTAL", "NET", "KG", "PCS"}
TICKER = re.compile(r"^[A-Z][A-Z0-9&\-]{0,9}(\.[A-Z]{1,3})?$|^\^[A-Z0-9]{2,8}$")


def unpivot_tickers(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """A price table with one column per share (Date, MSFT, IBM, AAPL ...): turn it into rows (Date, Symbol, Price)."""
    cols = [c for c in df.columns if c != "_row"]
    dates = [c for c in cols if looks_like_dates(df[c], str(c))]
    if len(dates) != 1:
        return df, None
    others = [c for c in cols if c not in dates]
    tick = [c for c in others if isinstance(c, str) and TICKER.match(c.strip()) and c.strip().upper() not in NOT_TICKERS
            and pd.to_numeric(df[c], errors="coerce").notna().mean() >= 0.8 * max(df[c].notna().mean(), 1e-9)]
    if len(tick) < 2 or len(tick) < 0.8 * len(others):
        return df, None
    long = df.melt(id_vars=dates + [c for c in others if c not in tick], value_vars=tick, var_name="Symbol", value_name="Price")
    long = long[long["Price"].notna()].reset_index(drop=True)
    if "_row" in df.columns:
        long["_row"] = np.arange(1, len(long) + 1)
    return long, f"The columns {', '.join(tick[:6])}{' ...' if len(tick) > 6 else ''} are {len(tick)} share prices side by side; turned them into rows (Date, Symbol, Price) so each can be followed and compared."

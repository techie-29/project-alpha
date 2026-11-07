"""Find, fix and report cell-level problems. See clean/__init__.py.

Two kinds of finding:
  * auto-fixes: safe and certain (an exact repeated row, 'bengaluru' next to 'Bengaluru', '1O00' typed with a letter O).
    They are applied and listed so the owner can see them.
  * decisions: things only the owner can judge (an age of -5, a date in month 13, a missing city). They are grouped by
    kind, each kind has one choice (blank them / remove the rows / keep), and a default that never loses data silently.

Everything is vectorised; a table of 10,000+ rows takes well under a second."""
from __future__ import annotations
import re
from difflib import SequenceMatcher
import numpy as np
import pandas as pd
from ..model.concepts import CONCEPTS
from ..understand.dates import read_dates
from ..understand.roles import MONEY, COUNT, PCT, PII_HEAD, header_tokens, id_header

EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
DATE_HEAD = re.compile(r"(date|dob|birth|timestamp|datetime|created|updated|joined|signup)", re.I)
MAY_BE_NEGATIVE = re.compile(r"(profit|margin|balance|refund|return|adjust|variance|change|diff|delta|growth|net|loss|credit|discount|ledger)", re.I)
TYPO_CELL = re.compile(r"^[\d.,\sOo\-₹$€£]+$")
MAX_AGE = 120
CELL_SAMPLE = 200            # cells per group sent to the screen (the counts are always complete)
PREVIEW_ROWS = 300

# type -> (title, plain explanation, choices [(id, label)], default). 'keep' never changes anything.
TYPES: dict[str, dict] = {
    "not_a_number": {"title": "Text where a number belongs", "why": "These cells hold words or symbols in a column of numbers.",
                     "choices": [("blank", "Blank them"), ("suggest", "Use suggested number"), ("remove", "Remove rows"), ("keep", "Keep")], "default": "blank"},
    "impossible_value": {"title": "Impossible values", "why": "Values outside what is possible for this column (for example an age below 0 or above 120).",
                         "choices": [("blank", "Blank them"), ("remove", "Remove rows"), ("keep", "Keep")], "default": "blank"},
    "invalid_date": {"title": "Dates that cannot be real", "why": "These cannot be read as a calendar date (for example month 13).",
                     "choices": [("blank", "Blank them"), ("remove", "Remove rows"), ("keep", "Keep")], "default": "blank"},
    "missing": {"title": "Missing values", "why": "The cell is empty although most rows in this column are filled.",
                "choices": [("keep", "Leave blank"), ("fill", "Fill text gaps with “Unknown”"), ("remove", "Remove rows")], "default": "keep"},
    "invalid_email": {"title": "Invalid email addresses", "why": "These do not look like an email address (no @ or no domain).",
                      "choices": [("keep", "Keep"), ("blank", "Blank it"), ("remove", "Remove rows")], "default": "keep"},
    "negative_value": {"title": "Negative amounts or counts", "why": "A negative amount can be a refund or a mistake; only you know.",
                       "choices": [("keep", "Keep (could be a refund)"), ("blank", "Blank it"), ("remove", "Remove rows")], "default": "keep"},
    "similar_spelling": {"title": "Similar spellings", "why": "A rare spelling sits next to a common one and is probably the same thing.",
                         "choices": [("keep", "Keep as they are"), ("merge", "Use the common spelling")], "default": "keep"},
    "duplicate_rows": {"title": "Repeated rows", "why": "Whole rows that appear more than once. In a log of events this can be real.",
                       "choices": [("keep", "Keep"), ("remove", "Remove the copies")], "default": "keep"},
    "outlier": {"title": "Extreme values", "why": "Far above or below everything else in the column. They may be real, but they can distort averages.",
                "choices": [("keep", "Keep"), ("blank", "Blank them"), ("remove", "Remove rows")], "default": "keep"},
}
DEFAULT_CHOICE = {k: v["default"] for k, v in TYPES.items()}
RESOLVES = {"blank", "remove", "fill", "merge", "suggest"}      # the choices that make the problem go away

_ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}


def _word_number(v: str):
    """'twenty' -> 20, 'twenty-five' -> 25, 'one hundred' -> 100. None when it is not a number written in words."""
    toks = re.split(r"[\s-]+", str(v).strip().lower())
    if not toks or any(t not in _ONES and t not in _TENS and t not in ("hundred", "and") for t in toks):
        return None
    total = cur = 0
    for t in toks:
        if t in _ONES:
            cur += _ONES[t]
        elif t in _TENS:
            cur += _TENS[t]
        elif t == "hundred":
            cur = max(cur, 1) * 100
    return total + cur


def _cells_to_numbers(x: pd.Series) -> pd.Series:
    """'1,200' / '₹500' / '(40)' / '12%' -> numbers; anything else -> NaN. Cells that are empty stay NaN."""
    t = x.astype(str).str.strip()
    neg = t.str.match(r"^\(.*\)$") | t.str.startswith("-")
    core = t.str.replace(r"^\((.*)\)$", r"\1", regex=True).str.replace(r"[\$€£₹¥,\s%]", "", regex=True).str.lstrip("-")
    v = pd.to_numeric(core, errors="coerce")
    return v.where(~neg, -v).where(x.notna())


def _is_text(s: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def _semantics(df: pd.DataFrame, hints: dict) -> dict[str, str]:
    """What kind of thing each column holds, only as far as cleaning needs: age, email, date, money, count, percent, number, id, category."""
    out: dict[str, str] = {}
    for c in df.columns:
        if c == "_row":
            continue
        s, toks, cid = df[c], header_tokens(c), hints.get(c)
        con = CONCEPTS.get(cid) if cid else None
        text = _is_text(s)
        nn = s.dropna()
        if nn.empty:
            continue
        sample = nn.head(300).astype(str)
        if pd.api.types.is_datetime64_any_dtype(s):
            continue                                                   # already real dates
        if "email" in toks or "mail" in toks or (text and sample.str.contains("@").mean() >= 0.6):
            out[c] = "email"; continue
        if cid == "age" or "age" in toks:
            out[c] = "age"; continue
        if (con is not None and con.kind == "date") or (text and DATE_HEAD.search(str(c)) and not (con is not None and con.kind != "date")):
            if text:
                out[c] = "date"
            continue
        if con is not None and con.kind == "key" or id_header(c):
            out[c] = "id"; continue
        if con is not None and con.kind == "number":
            out[c] = ("money" if con.money else "percent" if cid in ("discount_pct", "margin_pct", "percent") else
                      "count" if cid in ("quantity", "units_received", "units_ordered", "stock_level", "on_order", "activity_count", "points", "units_returned") else "number")
            continue
        if con is None:
            if MONEY.search(str(c)) and not PCT.search(str(c)):
                out[c] = "money"; continue
            if COUNT.search(str(c)):
                out[c] = "count"; continue
            if PCT.search(str(c)):
                out[c] = "percent"; continue
            if pd.api.types.is_numeric_dtype(s) and s.dtype != bool and not text:
                out[c] = "number"; continue
        if text and not PII_HEAD.search(str(c)) and 2 <= s.nunique() <= 300 and float(sample.str.len().mean()) <= 40 and (con is None or con.kind in ("group",)):
            out[c] = "category"
    return out


class _Found:
    def __init__(self, n: int):
        self.n = n
        self.items: list[dict] = []

    def add(self, typ: str, col: str | None, mask, original: pd.Series | None = None, suggest: pd.Series | None = None, extra: dict | None = None):
        m = np.asarray(mask, dtype=bool)
        if m.any():
            self.items.append({"type": typ, "column": col, "mask": m, "orig": original, "suggest": suggest, **(extra or {})})


def health(issues: int, cells: int) -> int:
    """0-100. Rounded down, and never 100 while any cell has a problem (300 problems in 70,000 cells is 99, not 100)."""
    if issues <= 0:
        return 100
    return max(0, min(99, int(100 * (1 - min(1.0, issues / max(1, cells))))))


def run(df: pd.DataFrame, name: str, notes: list[str] | None = None, hints: dict | None = None, decisions: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Returns (cleaned table, report). `decisions` maps a problem kind to the owner's choice; missing kinds use the safe default."""
    notes, hints, decisions = notes or [], hints or {}, {**DEFAULT_CHOICE, **(decisions or {})}
    df = df.reset_index(drop=True)
    n = len(df)
    cols = [c for c in df.columns if c != "_row"]
    rows_no = df["_row"].to_numpy() if "_row" in df.columns else np.arange(n) + 2
    sem = _semantics(df, hints)
    found = _Found(n)
    auto: list[dict] = []
    work = df.copy()

    # --- exact repeated rows: a few are copy mistakes (removed on their own); many may be real repeated events (the owner decides)
    dup = df.duplicated(subset=cols, keep="first").to_numpy() if cols else np.zeros(n, bool)
    auto_dup = np.zeros(n, bool)
    if dup.any():
        if dup.sum() <= max(3, int(0.02 * n)):
            auto_dup = dup
            auto.append({"id": "duplicate_rows", "what": f"Removed {int(dup.sum())} repeated row{'s' if dup.sum() > 1 else ''}", "count": int(dup.sum()), "kind": "rows",
                         "where": "Row " + ", ".join(str(int(r)) for r in rows_no[dup][:6]) + (" was" if dup.sum() == 1 else " were") + " an exact copy of an earlier row",
                         "examples": [{"row": int(r), "column": None, "from": "(whole row)", "to": None} for r in rows_no[dup][:20]]})
        else:
            found.add("duplicate_rows", None, dup)
    for note in notes:                                        # the reader may already have removed some
        m = re.search(r"Removed ([\d,]+) row\(s\) that were exact copies", note)
        if m:
            k = int(m.group(1).replace(",", ""))
            auto.append({"id": "duplicate_rows_read", "what": f"Removed {k:,} repeated row{'s' if k > 1 else ''} while reading the file", "count": k, "kind": "rows", "where": "Every column was identical to an earlier row", "examples": []})
    live = ~auto_dup                                          # problems on rows that are being removed anyway are not reported

    for c in cols:
        s, kind = df[c], sem.get(c)
        text = _is_text(s)
        present = s.notna().to_numpy()
        # --- numbers
        if kind in ("age", "money", "count", "percent", "number"):
            num = s.astype(float) if not text and pd.api.types.is_numeric_dtype(s) else _cells_to_numbers(s)
            if text:
                bad = present & num.isna().to_numpy()
                parsed_share = float((~bad[present]).mean()) if present.any() else 0
                if bad.any() and parsed_share >= 0.6:                      # mostly numbers: the others are mistakes
                    raw = s.astype(str)
                    fixed = raw.where(~bad, raw.str.replace("O", "0").str.replace("o", "0"))
                    can = bad & raw.str.match(TYPO_CELL).to_numpy() & raw.str.contains(r"\d").to_numpy()
                    renum = _cells_to_numbers(fixed.where(can))
                    ok = can & renum.notna().to_numpy() & live
                    if ok.any():                                            # '1O00' typed with a letter O: certain enough to fix
                        newtxt = renum[ok].map(lambda v: str(int(v)) if float(v).is_integer() else str(v))
                        work.loc[ok, c] = newtxt
                        auto.append({"id": f"typo:{c}", "what": f"Fixed {int(ok.sum())} typo{'s' if ok.sum() > 1 else ''} in “{c}” (letter O typed instead of zero)", "count": int(ok.sum()), "kind": "cells",
                                     "where": ", ".join(f"row {int(r)}" for r in rows_no[ok][:5]),
                                     "examples": [{"row": int(r), "column": c, "from": str(o), "to": t} for r, o, t in zip(rows_no[ok][:20], raw[ok].head(20), newtxt.head(20))]})
                        num = num.where(~ok, renum)
                        bad = bad & ~ok
                    sug = pd.Series(np.nan, index=df.index, dtype=object)
                    for i in np.flatnonzero(bad & live):
                        w = _word_number(s.iat[i])
                        if w is not None:
                            sug.iat[i] = w
                            num.iat[i] = float(w)
                    found.add("not_a_number", c, bad & live, s, sug)
                    num = num.where(~bad)
                elif parsed_share < 0.6:
                    continue
            v = num.to_numpy(dtype=float)
            fin = np.isfinite(v)
            if kind == "age":
                found.add("impossible_value", c, fin & ((v < 0) | (v > MAX_AGE)) & live, s)
            elif kind in ("money", "count") and not MAY_BE_NEGATIVE.search(str(c)) and not (CONCEPTS.get(hints.get(c)) is not None and hints.get(c) in ("profit", "refund", "discount")):
                found.add("negative_value", c, fin & (v < 0) & live, s)
            if kind in ("money", "count", "number") and fin.sum() >= 30:
                x = v[fin]
                med = float(np.median(x)); mad = float(np.median(np.abs(x - med)))
                if mad > 0:
                    z = np.abs(v - med) / (1.4826 * mad)
                    big = fin & (z > 12) & live
                    if 0 < big.sum() <= max(3, 0.01 * n):
                        found.add("outlier", c, big, s)
        # --- dates
        elif kind == "date" and text:
            tmp = s.dropna()
            if len(tmp) >= 1:
                r = read_dates(s, c, force=True)
                if r is not None:
                    bad = present & r.parsed.isna().to_numpy()
                    junk = s.astype(str).str.strip().isin(["", "-", "--", "N/A", "n/a", "NA", "null", "None", "0"]).to_numpy()
                    found.add("invalid_date", c, bad & ~junk & live, s)
        # --- emails
        elif kind == "email" and text:
            ok = s.astype(str).str.strip().str.match(EMAIL_OK).to_numpy()
            found.add("invalid_email", c, present & ~ok & live, s)
        # --- spelling of groups
        elif kind == "category" and text:
            vals = s.dropna().astype(str)
            vc = vals.value_counts()
            by_fold: dict[str, list[str]] = {}
            for val in vc.index:
                by_fold.setdefault(re.sub(r"\s+", " ", val.strip()).casefold(), []).append(val)
            canon: dict[str, str] = {}
            for fold, forms in by_fold.items():
                if len(forms) > 1:
                    best = max(forms, key=lambda f: (int(vc[f]), f != f.lower() and f != f.upper(), f))
                    for f in forms:
                        if f != best:
                            canon[f] = best
            if canon:
                m = s.isin(list(canon)).to_numpy() & live
                if m.any():
                    work.loc[m, c] = s[m].map(canon)
                    auto.append({"id": f"case:{c}", "what": f"Made spelling of “{c}” consistent ({int(m.sum())} cell{'s' if m.sum() > 1 else ''})", "count": int(m.sum()), "kind": "cells",
                                 "where": ", ".join(sorted({f"{a} → {b}" for a, b in canon.items()})[:3]),
                                 "examples": [{"row": int(r), "column": c, "from": str(o), "to": canon[str(o)]} for r, o in zip(rows_no[m][:20], s[m].head(20))]})
            keys = [k for k in by_fold if len(k) >= 5]
            if 2 <= len(keys) <= 300:
                total = {k: int(vc[by_fold[k]].sum()) for k in keys}
                rare_to_common: dict[str, str] = {}
                for i, a in enumerate(keys):
                    for b in keys[i + 1:]:
                        if abs(len(a) - len(b)) <= 2 and SequenceMatcher(None, a, b).ratio() >= 0.88:
                            lo, hi = (a, b) if total[a] <= total[b] else (b, a)
                            if total[lo] <= 0.2 * total[hi]:
                                for f in by_fold[lo]:
                                    rare_to_common[f] = max(by_fold[hi], key=lambda x: int(vc[x]))
                if rare_to_common:
                    m = s.isin(list(rare_to_common)).to_numpy() & live
                    sug = s.map(rare_to_common)
                    found.add("similar_spelling", c, m, s, sug)
        # --- missing
        miss = (~present) & live
        share = float((~present).mean()) if n else 0.0
        if miss.any() and share < 0.5:                       # a column filled on under half the rows is an optional detail, not missing data
            found.add("missing", c, miss, s, extra={"textual": bool(text)})

    # ---------- combine: what the owner chose for each kind
    drop = auto_dup.copy()
    blank_cells: list[tuple[str, np.ndarray]] = []
    groups, issue_cells = [], 0
    flagged_rows: set[int] = set()
    by_type: dict[str, list[dict]] = {}
    for it in found.items:
        by_type.setdefault(it["type"], []).append(it)
    cell_touch = np.zeros(n, bool)
    for typ in TYPES:
        its = by_type.get(typ)
        if not its:
            continue
        choice = decisions.get(typ, TYPES[typ]["default"])
        if choice not in [cid for cid, _ in TYPES[typ]["choices"]]:
            choice = TYPES[typ]["default"]
        cells, count, grows = [], 0, set()
        for it in its:
            m, col = it["mask"], it["column"]
            idx = np.flatnonzero(m)
            count += len(idx)
            grows.update(int(r) for r in rows_no[idx][:5000])
            issue_cells += len(idx) if col else int(m.sum())
            for i in idx:
                flagged_rows.add(int(rows_no[i]))
            if len(cells) < CELL_SAMPLE:
                for i in idx[: CELL_SAMPLE - len(cells)]:
                    sg = it["suggest"].iat[i] if it.get("suggest") is not None else None
                    cells.append({"row": int(rows_no[i]), "column": col, "value": None if it["orig"] is None else (None if pd.isna(it["orig"].iat[i]) else str(it["orig"].iat[i])),
                                  "suggest": None if sg is None or (isinstance(sg, float) and np.isnan(sg)) else str(int(sg) if isinstance(sg, (int, float, np.integer, np.floating)) and float(sg).is_integer() else sg)})
            if choice == "remove":
                drop |= m
            elif choice == "blank" and col:
                blank_cells.append((col, m))
            elif choice == "fill" and col and it.get("textual"):
                blank_cells.append((col + "\u0000fill", m))
            elif choice == "merge" and col and it.get("suggest") is not None:
                work.loc[m, col] = it["suggest"][m]
            elif choice == "suggest" and col and it.get("suggest") is not None:
                sg = it["suggest"]
                has = sg.notna().to_numpy() & m
                work.loc[has, col] = sg[has].map(lambda v: str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v))
                blank_cells.append((col, m & ~has))
            elif choice == "remove":
                drop |= m
        if typ == "duplicate_rows":
            cells = [{"row": int(rows_no[i]), "column": None, "value": "(whole row)", "suggest": None} for i in np.flatnonzero(its[0]["mask"])[:CELL_SAMPLE]]
        groups.append({"type": typ, "title": TYPES[typ]["title"], "why": TYPES[typ]["why"], "count": count, "choice": choice, "default": TYPES[typ]["default"],
                       "choices": [{"id": cid, "label": lab, "resolves": cid in RESOLVES} for cid, lab in TYPES[typ]["choices"]
                                   if not (cid == "suggest" and not any(i.get("suggest") is not None and i["suggest"].notna().any() for i in its))
                                   and not (cid == "fill" and not any(i.get("textual") for i in its))],
                       "cells": cells, "columns": sorted({i["column"] for i in its if i["column"]}), "rows": sorted(grows)})
    for col, m in blank_cells:
        if col.endswith("\u0000fill"):
            work.loc[m, col.split("\u0000")[0]] = "Unknown"
        else:
            work.loc[m, col] = np.nan
    removed = int(drop.sum())
    if removed:
        work = work[~drop]
    work = work.reset_index(drop=True)

    auto_cells = sum(a["count"] if a["kind"] == "cells" else 1 * a["count"] for a in auto if a["id"] != "duplicate_rows_read")
    total_cells = max(1, n * max(1, len(cols)))
    health_now = health(issue_cells + auto_cells, total_cells)
    read_dups = sum(a["count"] for a in auto if a["id"] == "duplicate_rows_read")     # removed by the reader: counted as fixed, not in the cell score

    # ---------- preview table: the original values, with each problem cell marked
    marks: dict[tuple[int, str], dict] = {}
    for it in found.items:
        if it["column"]:
            for i in np.flatnonzero(it["mask"]):
                marks[(int(i), it["column"])] = {"s": "issue", "t": it["type"]}
    for a in auto:
        for e in a["examples"]:
            if e["column"]:
                i = int(np.flatnonzero(rows_no == e["row"])[0]) if (rows_no == e["row"]).any() else None
                if i is not None:
                    marks[(i, e["column"])] = {"s": "fixed", "t": a["id"].split(":")[0], "to": e["to"]}
    problem_rows = sorted({i for i, _ in marks} | set(np.flatnonzero(dup).tolist()))
    pick = problem_rows[:PREVIEW_ROWS] if n > PREVIEW_ROWS else list(range(n))
    if n > PREVIEW_ROWS and len(pick) < PREVIEW_ROWS:
        extra = [i for i in range(n) if i not in set(pick)][: PREVIEW_ROWS - len(pick)]
        pick = sorted(pick + extra)
    prow = []
    for i in pick:
        cells_out = []
        for c in cols:
            val = df[c].iat[i]
            shown = None if pd.isna(val) else (val.strftime("%Y-%m-%d") if hasattr(val, "strftime") else str(val))
            cell = {"v": shown}
            cell.update(marks.get((i, c), {}))
            cells_out.append(cell)
        prow.append({"row": int(rows_no[i]), "cells": cells_out, "repeat": bool(dup[i]), "removed": bool(drop[i])})
    report = {
        "file": name, "rows": n, "columns": cols, "cells": total_cells, "semantics": sem,
        "auto": auto, "groups": groups,
        "summary": {"issues": issue_cells + auto_cells + read_dups,
                    "auto": auto_cells + read_dups, "decisions": issue_cells, "problem_rows": len(flagged_rows),
                    "rows_before": n, "rows_after": int(len(work)), "removed": removed, "health": health_now},
        "preview": {"columns": cols, "rows": prow, "shown": len(prow), "total": n},
        "flagged_rows": sorted(flagged_rows)[:5000],
    }
    return work, report

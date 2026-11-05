"""Data validation for any business file: 26 checks in 7 groups, a status for every row, and a reconciliation of what
came in against what is counted.

Principles
  * Nothing is silently deleted or invented. Each check says what it found, how many rows, how much money sits in those
    rows, and gives example rows with their row number in the original file.
  * Every row ends with one status: ok, fixed (a value was cleaned, e.g. '1,200' -> 1200), flagged (kept, but a check
    failed), or left out (and why: cancelled/returned, a total row, an exact copy).
  * Checks run only when the file has what they need; otherwise they say 'not applicable' rather than 'passed'.
  * Business rules (profit <= sale, ...) are only applied when the columns were read with that meaning, and rules that
    should hold 'for most rows' are first checked to hold before outliers are called errors."""
from __future__ import annotations
import re
from difflib import SequenceMatcher
import numpy as np
import pandas as pd
from ..understand.roles import clean_numeric
from ..model.concepts import CONCEPTS

# (id, group, title) - the order is the order shown to the owner
CHECKS = [
    ("header_offset", "File structure", "Title lines above the header"),
    ("total_rows", "File structure", "Total or subtotal rows inside the data"),
    ("empty", "File structure", "Empty rows and columns"),
    ("duplicate_columns", "File structure", "Columns with the same name"),
    ("missing_values", "Missing data", "Missing values per column"),
    ("missing_key_fields", "Missing data", "Rows missing a key field (date, amount, product, customer)"),
    ("time_gaps", "Missing data", "Gaps in time"),
    ("partial_periods", "Missing data", "Incomplete first or last period"),
    ("duplicate_rows", "Duplicates", "Rows that are exact copies"),
    ("duplicate_ids", "Duplicates", "Repeated IDs that should be unique"),
    ("overlapping_files", "Duplicates", "The same rows in two files"),
    ("text_in_numbers", "Format and type", "Text or symbols inside number columns"),
    ("unreadable_dates", "Format and type", "Dates that cannot be read"),
    ("dates_out_of_range", "Format and type", "Dates in the future or implausibly old"),
    ("group_variants", "Format and type", "Different spellings of the same group"),
    ("mixed_scales", "Format and type", "Percentages written two ways (0.05 and 5)"),
    ("profit_above_sale", "Business rules", "Profit larger than the sale"),
    ("negative_values", "Business rules", "Negative prices, costs or quantities"),
    ("sale_vs_qty_price", "Business rules", "Sale far from units x price"),
    ("profit_vs_cost", "Business rules", "Profit different from sale minus cost"),
    ("discount_range", "Business rules", "Discounts below 0, above 100% or above the price"),
    ("date_order", "Business rules", "A later step dated before an earlier one"),
    ("product_conflicts", "Business rules", "One product code with different names or very different prices"),
    ("status_conflicts", "Business rules", "Status that contradicts other columns"),
    ("extreme_values", "Unusual values", "Extreme single values and sudden changes of scale"),
    ("orphan_codes", "Across files", "Codes that do not exist in the linked list"),
]
TITLE = {c: t for c, _, t in CHECKS}
GROUP = {c: g for c, g, _ in CHECKS}
EXAMPLES = 25                                    # example rows kept per check (all row numbers are kept separately)


def _num(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s) and s.dtype != bool:
        return s.astype(float)
    v = clean_numeric(s)
    return v.astype(float) if v is not None else pd.to_numeric(s, errors="coerce")


class _Run:
    """Collects results for one file."""

    def __init__(self, name: str, df: pd.DataFrame, money: pd.Series | None, cur: str | None):
        self.name, self.df, self.money, self.cur = name, df, money, cur
        self.results: dict[str, dict] = {}
        self.flag = pd.Series("", index=df.index, dtype=object)     # which checks each row failed
        self.fixed = pd.Series(False, index=df.index)

    def money_in(self, mask: pd.Series) -> float | None:
        if self.money is None or not mask.any():
            return None
        v = float(self.money[mask].sum())
        return v if np.isfinite(v) else None

    def examples(self, mask: pd.Series, cols: list[str]) -> dict:
        cols = [c for c in dict.fromkeys(["_row"] + cols) if c in self.df.columns]
        sub = self.df.loc[mask, cols].head(EXAMPLES)
        rows = sub.astype(object).where(sub.notna(), None).values.tolist()
        return {"columns": ["Row in file" if c == "_row" else c for c in cols], "rows": rows,
                "all_rows": [int(x) for x in self.df.loc[mask, "_row"].tolist()[:5000]] if "_row" in self.df.columns else []}

    def put(self, cid: str, status: str, detail: str, mask: pd.Series | None = None, cols: list[str] | None = None,
            n: int | None = None, money: float | None = None, fix: str | None = None, extra: dict | None = None, flag_rows: bool = True):
        """status: pass | fixed | warn | fail | info | n/a"""
        r = {"id": cid, "group": GROUP[cid], "title": TITLE[cid], "status": status, "detail": detail, "file": self.name}
        if mask is not None:
            mask = mask.reindex(self.df.index, fill_value=False).fillna(False).astype(bool)
            r["rows"] = int(mask.sum())
            r["share"] = round(float(mask.mean()), 4) if len(mask) else 0.0
            r["money"] = self.money_in(mask) if money is None else money
            r["examples"] = self.examples(mask, cols or [])
            if status in ("warn", "fail") and flag_rows:
                cur = self.flag[mask]
                self.flag[mask] = np.where(cur == "", cid, cur + "," + cid)
            if status == "fixed":
                self.fixed |= mask
        elif n is not None:
            r["rows"] = int(n)
            if money is not None:
                r["money"] = money
        if fix:
            r["fix"] = fix
        if extra:
            r.update(extra)
        if cid in self.results:                                   # several findings for one check (e.g. two columns)
            old = self.results[cid]
            order = ["n/a", "pass", "info", "fixed", "warn", "fail"]
            old["status"] = max(old["status"], status, key=order.index)
            old.setdefault("parts", []).append(r)
            old["rows"] = int(old.get("rows") or 0) + int(r.get("rows") or 0)
            old["detail"] = old["detail"] + " " + detail
            if r.get("money"):
                old["money"] = (old.get("money") or 0) + r["money"]
        else:
            self.results[cid] = r


# ------------------------------------------------------------------------------------------------ the checks
NOTE_NUM = re.compile(r"([\d,]+)")


def _from_notes(R: _Run, notes: list[str]) -> dict:
    """What the file reader already fixed while opening the file (it leaves plain-language notes)."""
    out = {"dropped_duplicates": 0, "dropped_totals": 0}
    joined = " ".join(notes)
    m = re.search(r"Skipped (\d+) line\(s\) above the header", joined)
    R.put("header_offset", "fixed" if m else "pass",
          f"{m.group(1)} line(s) of titles or notes above the header were skipped; data starts below them." if m else "The header is on the first line.",
          n=int(m.group(1)) if m else 0, fix="skipped" if m else None)
    m = re.search(r"Left out (\d+) total/summary row\(s\)( \(source rows ([\d, ]+)\))?", joined)
    if m:
        out["dropped_totals"] = int(m.group(1))
        R.put("total_rows", "fixed", f"{m.group(1)} total/summary row(s) were left out so nothing is counted twice"
              + (f" (rows {m.group(3)})." if m.group(3) else "."), n=int(m.group(1)), fix="left out")
    else:
        R.put("total_rows", "pass", "No total or subtotal rows found inside the data.", n=0)
    m = re.search(r"Removed ([\d,]+) row\(s\) that were exact copies", joined)
    k = re.search(r"([\d,]+) rows \((\d+)%\) are exact copies of other rows\. They were kept", joined)
    if m:
        out["dropped_duplicates"] = int(m.group(1).replace(",", ""))
        R.put("duplicate_rows", "fixed", f"{m.group(1)} row(s) were exact copies of another row (every column the same) and were left out.", n=out["dropped_duplicates"], fix="left out")
    elif k:
        R.put("duplicate_rows", "warn", f"{k.group(1)} rows ({k.group(2)}%) are exact copies of other rows. They were kept because so many copies may be real "
              "repeated events (e.g. the same item sold twice in a minute); check at the source.", n=int(k.group(1).replace(",", "")))
    else:
        R.put("duplicate_rows", "pass", "No row is an exact copy of another.", n=0)
    m = re.search(r"Dropped (\d+) empty column\(s\)", joined)
    R.put("empty", "fixed" if m else "pass", f"{m.group(1)} column(s) with no values were left out; fully empty rows are skipped when reading." if m
          else "No empty columns; fully empty rows are skipped when reading.", n=0, fix="left out" if m else None)
    case = re.findall(r"'([^']+)': values that differ only in capitals", joined)
    out["case_merged"] = case
    return out


def _structure(R: _Run, p):
    d = R.df
    base = {}
    for c in d.columns:
        m = re.match(r"^(.*)_(\d+)$", str(c))
        if m and m.group(1) in d.columns:
            base.setdefault(m.group(1), []).append(c)
    if base:
        txt = "; ".join(f"'{b}' appears {len(v) + 1} times (read as {', '.join([b] + v)})" for b, v in base.items())
        R.put("duplicate_columns", "warn", f"{txt}. Check which one holds the real values.", n=0)
    else:
        R.put("duplicate_columns", "pass", "Every column has its own name.", n=0)


def _missing(R: _Run, p, concept_of: dict):
    d = R.df
    cols = [c for c in d.columns if not str(c).startswith("_") and c in p.roles and p.roles[c].get("role") not in ("empty", "constant")]
    worst, parts = None, []
    for c in cols:
        miss = d[c].isna()
        if p.roles[c].get("role") == "measure" and not pd.api.types.is_numeric_dtype(d[c]):
            miss = miss | _num(d[c]).isna()
        share = float(miss.mean())
        key = concept_of.get(c) in ("revenue", "profit", "quantity", "order_id", "product_id", "customer_id", "event_date", "cost")
        if share >= 0.01 or (key and miss.any()):
            parts.append((c, share, miss))
    if not parts:
        R.put("missing_values", "pass", "Every column is filled on at least 99% of rows.", n=0)
    else:
        parts.sort(key=lambda x: -x[1])
        for c, share, miss in parts[:12]:
            key = concept_of.get(c) in ("revenue", "profit", "quantity", "order_id", "product_id", "customer_id", "event_date", "cost")
            status = "warn" if (share >= 0.05 and key) or share >= 0.3 else "info"
            m = R.money_in(miss)
            R.put("missing_values", status, f"'{c}' is empty on {share:.1%} of rows ({int(miss.sum()):,})"
                  + (f", rows carrying {m:,.2f} of sales." if m else "."), mask=miss, cols=[c], flag_rows=key)
    # rows missing something every analysis needs
    need = {k: c for c, k in concept_of.items() if k in ("revenue", "event_date", "product_id", "customer_id") and c in d.columns}
    if p.time_col in d.columns:
        need["event_date"] = p.time_col
    if need:
        mk = pd.Series(False, index=d.index)
        what = []
        for k, c in need.items():
            v = d["_t"] if k == "event_date" and "_t" in d.columns else (_num(d[c]) if k == "revenue" else d[c])
            m = v.isna()
            if m.any():
                mk |= m; what.append(f"{CONCEPTS[k].label.lower()} ({int(m.sum()):,})")
        if mk.any():
            R.put("missing_key_fields", "warn", f"{int(mk.sum()):,} rows lack a key field: {', '.join(what)}. They are left out of the analyses that need that field.",
                  mask=mk, cols=list(need.values()))
        else:
            R.put("missing_key_fields", "pass", "Every row has its " + ", ".join(CONCEPTS[k].label.lower() for k in need) + ".", n=0)
    else:
        R.put("missing_key_fields", "n/a", "No date, amount, product or customer column to check.")


def _time(R: _Run, p):
    d = R.df
    if "_t" not in d.columns or not d["_t"].notna().any() or getattr(p, "synthetic_time", False):
        for cid in ("time_gaps", "partial_periods"):
            R.put(cid, "n/a", "The file has no timeline.")
        return
    t = d["_t"].dropna()
    span = (t.max() - t.min()).days
    grain, freq = ("day", "D") if span <= 120 else ("month", "M")
    per = t.dt.to_period(freq)
    counts = per.value_counts().sort_index()
    full = pd.period_range(counts.index.min(), counts.index.max(), freq=freq)
    counts = counts.reindex(full, fill_value=0)
    typical = float(counts[counts > 0].median()) if (counts > 0).any() else 0
    gaps = [str(x) for x, v in counts.items() if v == 0]
    if grain == "day":                                             # closed days are normal; only long runs of missing days matter
        z = (counts == 0).astype(int).to_numpy()
        runs, run = [], 0
        for i, v in enumerate(z):
            run = run + 1 if v else 0
            if run == 4:
                runs.append(str(full[i - 3]))
        gaps = runs
    if gaps and typical >= 3:
        R.put("time_gaps", "warn", f"No rows at all for {len(gaps)} {'stretch(es) of 4+ days' if grain == 'day' else 'month(s)'} inside the period "
              f"(e.g. {', '.join(gaps[:4])}), while a typical {grain} has about {typical:.0f} rows. A drop there may be missing data, not a real fall.",
              n=0, extra={"periods": gaps[:24]})
    else:
        R.put("time_gaps", "pass", f"Every {grain} between the first and last date has rows.", n=0)
    # first / last period only partly covered (a half month looks like a drop)
    if grain == "month" and len(full) >= 3:
        notes = []
        first, last = t.min(), t.max()
        dim_last, dim_first = last.days_in_month, first.days_in_month
        if last.day < 0.85 * dim_last:
            notes.append(f"the last month ({last:%b %Y}) only runs to day {last.day} of {dim_last}")
        if first.day > 1 + 0.15 * dim_first:
            notes.append(f"the first month ({first:%b %Y}) starts on day {first.day}")
        if notes:
            R.put("partial_periods", "warn", "Partly covered months: " + "; ".join(notes) + ". Totals for those months are incomplete, so a "
                  "low figure there is not a real fall. Compare them with care.", n=0, extra={"partial": notes})
        else:
            R.put("partial_periods", "pass", "The first and last months are fully covered.", n=0)
    else:
        R.put("partial_periods", "n/a" if grain == "day" else "pass", "Short period: looked at day by day." if grain == "day" else "Fewer than 3 months: not checked.")


def _duplicate_ids(R: _Run, p, concept_of: dict, role: dict):
    d = R.df
    oid = next((c for c, k in concept_of.items() if k == "order_id" and c in d.columns), None)
    pid = next((c for c, k in concept_of.items() if k == "product_id" and c in d.columns), None)
    if role.get("role") == "master" and role.get("key") in d.columns:
        k = role["key"]
        dup = d[k].duplicated(keep=False) & d[k].notna()
        R.put("duplicate_ids", "warn" if dup.any() else "pass", f"{int(dup.sum()):,} rows share a {k} with another row in what should be a list with one row each."
              if dup.any() else f"Each {k} appears once.", mask=dup if dup.any() else None, cols=[k], n=0 if not dup.any() else None)
        return
    if oid is None:
        R.put("duplicate_ids", "n/a", "No order or invoice number to check.")
        return
    one_per_order = d[oid].nunique() >= 0.95 * d[oid].notna().sum()
    keys = [oid] if one_per_order else [oid] + ([pid] if pid else [])     # one row per order: the order number alone must be unique
    if pid is None and not one_per_order:
        R.put("duplicate_ids", "info", f"'{oid}' repeats across rows: the file has several lines per order (normal for item-level exports).", n=0)
        return
    dup = d.duplicated(subset=keys, keep=False) & d[oid].notna()
    if dup.any():
        R.put("duplicate_ids", "warn", f"{int(dup.sum()):,} rows repeat the same {' + '.join(keys)}. If each should appear once, totals are overstated by these rows.",
              mask=dup, cols=keys)
    else:
        R.put("duplicate_ids", "pass", f"No {' + '.join(keys)} appears twice.", n=0)


def _text_in_numbers(R: _Run, p, concept_of: dict):
    """prepare() converts number columns written as text and records, row by row, what it cleaned and what it could not read."""
    issues = getattr(p, "text_issues", {}) or {}
    found = False
    for c, t in issues.items():
        if c not in R.df.columns or len(t["cleaned"]) != len(R.df):
            continue
        cleaned = pd.Series(t["cleaned"], index=R.df.index)
        bad = pd.Series(t["unreadable"], index=R.df.index)
        if cleaned.any():
            found = True
            R.put("text_in_numbers", "fixed", f"'{c}': {int(cleaned.sum()):,} values written with symbols or separators (e.g. {', '.join(t['examples_cleaned'])}) "
                  "were read as numbers.", mask=cleaned, cols=[c], fix="cleaned")
        if bad.any():
            found = True
            R.put("text_in_numbers", "warn", f"'{c}': {int(bad.sum()):,} values are not numbers (e.g. {', '.join(t['examples_unreadable'])}) and are treated as empty.",
                  mask=bad, cols=[c])
    if not found:
        R.put("text_in_numbers", "pass", "Number columns hold plain numbers.", n=0)


def _dates(R: _Run, p, concept_of: dict):
    d = R.df
    dcols = [c for c, i in p.roles.items() if i.get("role") == "time" and c in d.columns]
    if not dcols:
        R.put("unreadable_dates", "n/a", "No date columns."); R.put("dates_out_of_range", "n/a", "No date columns.")
        return
    bad_any = False
    for c in dcols:
        i = p.roles[c]
        junk = int(i.get("date_junk") or 0)
        rate = i.get("parse_rate")
        nn = int(i.get("non_null") or 0)
        unread = int(round((1 - rate) * nn)) if rate is not None else 0
        if unread > 0:
            bad_any = True
            R.put("unreadable_dates", "warn", f"'{c}': {unread:,} value(s) could not be read as dates and are treated as empty.", n=unread)
        if junk:
            R.put("unreadable_dates", "info", f"'{c}': {junk:,} blank markers (N/A, -, 0...) treated as no date.", n=junk)
        if i.get("date_order") in ("day-first", "month-first") and not i.get("date_certain"):
            bad_any = True
            R.put("unreadable_dates", "warn", f"'{c}': day and month could be either way round; read {i['date_order']} (e.g. {i.get('date_example', '')}). Please confirm.", n=0)
    if not bad_any and "unreadable_dates" not in R.results:
        R.put("unreadable_dates", "pass", "Every date could be read, and the day/month order is certain.", n=0)
    now = pd.Timestamp.now().normalize()
    future_ok = re.compile(r"(expir|due|deadline|valid|renew|expected|planned|promised|end)", re.I)
    found = False
    for c in dcols:
        s = d[c] if pd.api.types.is_datetime64_any_dtype(d[c]) else pd.to_datetime(d[c], errors="coerce")
        fut = s > now + pd.Timedelta(days=1)
        old = s < pd.Timestamp("1990-01-01")
        if concept_of.get(c) in ("expiry_date", "due_date") or future_ok.search(str(c)):
            fut = pd.Series(False, index=d.index)
        if concept_of.get(c) == "signup_date" or re.search(r"birth|dob", str(c), re.I):
            old = s < pd.Timestamp("1900-01-01")
        m = (fut | old).fillna(False)
        if m.any():
            found = True
            R.put("dates_out_of_range", "warn", f"'{c}': {int(fut.sum()):,} date(s) in the future and {int(old.sum()):,} before 1990.", mask=m, cols=[c])
    if not found:
        R.put("dates_out_of_range", "pass", "No dates in the future or implausibly far back.", n=0)


def _norm_label(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(v).casefold())


def _variants(R: _Run, p, merged_case: list[str]):
    d = R.df
    cols = [c for c, i in p.roles.items() if i.get("role") == "category" and c in d.columns and 2 <= int(i.get("unique") or 0) <= 300]
    found = False
    for c in merged_case:
        if c in d.columns:
            R.put("group_variants", "fixed", f"'{c}': values that differ only in capitals were merged (e.g. 'north' and 'North').", n=0, fix="merged")
            found = True
    for c in cols:
        vc = d[c].dropna().astype(str).value_counts()
        groups: dict[str, list[str]] = {}
        for v in vc.index:
            groups.setdefault(_norm_label(v), []).append(v)
        same = {k: v for k, v in groups.items() if len(v) > 1 and k}
        keys = [k for k in groups if k]
        near = []
        if len(keys) <= 300:
            for a_i, a in enumerate(keys):
                for b in keys[a_i + 1:]:
                    if min(len(a), len(b)) >= 5 and abs(len(a) - len(b)) <= 2 and SequenceMatcher(None, a, b).ratio() >= 0.9:
                        ca, cb = int(vc[groups[a]].sum()), int(vc[groups[b]].sum())
                        if min(ca, cb) <= 0.1 * max(ca, cb):            # a rare spelling next to a common one
                            near.append((groups[a][0], groups[b][0], ca, cb))
        if same or near:
            found = True
            ex = [" / ".join(v[:3]) for v in list(same.values())[:3]] + [f"{a} / {b}" for a, b, _, _ in near[:3]]
            vals = [x for v in same.values() for x in v] + [x for a, b, ca, cb in near for x in ((a,) if ca < cb else (b,))]
            mask = d[c].astype(str).isin(vals)
            R.put("group_variants", "warn", f"'{c}': the same group seems written more than one way ({'; '.join(ex)}). They are counted as separate groups "
                  "until you merge them.", mask=mask, cols=[c], flag_rows=False)
    if not found:
        R.put("group_variants", "pass", "No group is written in more than one way.", n=0)


def _mixed_scales(R: _Run, p, concept_of: dict):
    """Looks at the values as they are in the file (the frame has already converted them)."""
    cols = [c for c, k in concept_of.items() if k in ("discount_pct", "margin_pct", "percent") and c in R.df.columns]
    found = False
    for c in cols:
        v = _num(R.df[c])
        nz = v[v.notna() & (v != 0)]
        if len(nz) < 20:
            continue
        small, big = (nz.abs() <= 1), (nz.abs() > 1.5)
        # both ways present: at least 3 rows of the rarer kind (even a handful of '5' among '0.05' distorts every average)
        if min(int(small.sum()), int(big.sum())) >= 3 and max(small.mean(), big.mean()) >= 0.5:
            found = True
            shares_win = small.sum() >= big.sum()
            minority = big if shares_win else small
            m = pd.Series(False, index=R.df.index); m.loc[minority[minority].index] = True
            if concept_of.get(c) == "discount_pct" and shares_win:
                R.put("mixed_scales", "fixed", f"'{c}': {int(small.sum()):,} values are written as shares (0.05) and {int(big.sum()):,} as percents (5). "
                      f"The percents were read as shares (5 -> 0.05) so all rows use one scale.", mask=m, cols=[c], fix="converted")
            else:
                R.put("mixed_scales", "warn", f"'{c}': {int(small.sum()):,} values look like shares (0.05) and {int(big.sum()):,} like percents (5). "
                      "One of the two is probably a mistake; averages mix both.", mask=m, cols=[c])
    if not found:
        R.put("mixed_scales", "pass" if cols else "n/a", "Percentages are written one way." if cols else "No percentage columns.", n=0)


def _rules(R: _Run, F, cur, items_out: list):
    """Business rules on the meaning of the columns. Reuses the existing impossible-value checks and adds the rest."""
    from ..analyses import validity
    if F is None:
        for cid in ("profit_above_sale", "negative_values", "sale_vs_qty_price", "profit_vs_cost", "discount_range", "date_order", "product_conflicts"):
            R.put(cid, "n/a", "No columns with these meanings.")
        return
    d = F.df
    items = validity.run(F, cur)
    items_out.extend(items)
    flags = d.get(validity.FLAG, pd.Series("", index=d.index)).astype(str)
    col = lambda k: F.canon.get(k, k) if isinstance(F.canon.get(k), str) and F.canon.get(k) in R.df.columns else k
    by_code = {}
    for i in items:
        by_code.setdefault((i.get("numbers") or {}).get("check"), []).append(i)

    def mask_of(code):
        m = flags.str.contains(code, regex=False)
        return pd.Series(m.to_numpy(), index=R.df.index[:len(m)]) if len(m) == len(R.df) else m.reindex(R.df.index, fill_value=False)

    # 17 profit above sale
    if {"profit", "revenue"} <= set(d.columns):
        if "profit_above_sale" in by_code:
            i = by_code["profit_above_sale"][0]
            R.put("profit_above_sale", "fail", i["detail"], mask=mask_of("profit_above_sale"), cols=[col("revenue"), col("profit")],
                  money=(i.get("numbers") or {}).get("sales_on_rows"), extra={"numbers": i.get("numbers")})
        else:
            R.put("profit_above_sale", "pass", "No row shows more profit than its own sale.", n=0)
    else:
        R.put("profit_above_sale", "n/a", "Needs both a sale and a profit column.")
    # 18 negatives: prices/costs are errors; quantities below zero are usually returns
    neg_found = False
    for code, k in (("negative_unit_price", "unit_price"), ("negative_unit_cost", "unit_cost")):
        if code in by_code:
            neg_found = True
            R.put("negative_values", "fail", by_code[code][0]["detail"], mask=mask_of(code), cols=[col(k)])
    if "quantity" in d.columns:
        q = d["quantity"]
        neg = (q < 0).fillna(False)
        if neg.any():
            neg_found = True
            m = pd.Series(neg.to_numpy(), index=R.df.index) if len(neg) == len(R.df) else neg
            R.put("negative_values", "info", f"{int(neg.sum()):,} rows have a negative quantity. These are usually returns or corrections; they reduce the totals "
                  "as they should, but check they are not entry mistakes.", mask=m, cols=[col("quantity")], flag_rows=False)
    for k in ("revenue", "cost"):
        if k in d.columns and (d[k] < 0).mean() > 0:
            neg = (d[k] < 0).fillna(False)
            neg_found = True
            R.put("negative_values", "info", f"{int(neg.sum()):,} rows have a negative {CONCEPTS[k].label.lower()} (refunds or credit notes, usually).",
                  mask=pd.Series(neg.to_numpy(), index=R.df.index), cols=[col(k)], flag_rows=False)
    if not neg_found:
        R.put("negative_values", "pass" if set(d.columns) & {"unit_price", "unit_cost", "quantity", "revenue"} else "n/a", "No negative prices, costs or quantities.", n=0)
    # 19 sale vs units x price
    if {"revenue", "quantity", "unit_price"} <= set(d.columns):
        if "sale_vs_qty_price" in by_code:
            R.put("sale_vs_qty_price", "warn", by_code["sale_vs_qty_price"][0]["detail"], mask=mask_of("sale_vs_qty_price"), cols=[col("revenue"), col("quantity"), col("unit_price")])
        else:
            R.put("sale_vs_qty_price", "pass", "Where sales follow units x price, every row agrees (or the file does not follow that rule).", n=0)
    else:
        R.put("sale_vs_qty_price", "n/a", "Needs sale, units and unit price.")
    # 20 profit = sale - cost (only when that holds for most rows)
    if {"profit", "revenue", "cost"} <= set(d.columns):
        diff = d["revenue"] - d["cost"] - d["profit"]
        tol = 0.02 * d["revenue"].abs() + 0.05
        ok = diff.abs() <= tol
        if ok.mean() >= 0.8:
            off = (~ok & d["revenue"].notna() & d["profit"].notna()).fillna(False)
            m = pd.Series(off.to_numpy(), index=R.df.index)
            if off.any():
                R.put("profit_vs_cost", "warn", f"For {ok.mean():.0%} of rows profit = sale - cost; {int(off.sum()):,} rows do not add up.", mask=m,
                      cols=[col("revenue"), col("cost"), col("profit")])
            else:
                R.put("profit_vs_cost", "pass", "Profit equals sale minus cost on every row.", n=0)
        else:
            R.put("profit_vs_cost", "info", f"Profit equals sale minus cost on only {ok.mean():.0%} of rows: the file's profit includes other costs, so this rule is not applied.", n=0)
    else:
        R.put("profit_vs_cost", "n/a", "Needs sale, cost and profit.")
    # 21 discount range
    rng = []
    if "discount_out_of_range" in by_code:
        rng.append(mask_of("discount_out_of_range"))
    if {"discount", "gross_revenue"} <= set(d.columns):
        over = (d["discount"] > d["gross_revenue"] + 0.01).fillna(False)
        if over.any():
            rng.append(pd.Series(over.to_numpy(), index=R.df.index))
    if rng:
        m = rng[0]
        for x in rng[1:]:
            m = m | x
        R.put("discount_range", "fail", f"{int(m.sum()):,} rows have a discount below 0%, above 100%, or larger than the price.", mask=m,
              cols=[col(k) for k in ("discount_pct", "discount", "gross_revenue") if k in d.columns])
    else:
        R.put("discount_range", "pass" if set(d.columns) & {"discount_pct", "discount"} else "n/a", "Every discount is between 0% and 100% of the price.", n=0)
    # 22 date order
    if "date_order" in by_code:
        R.put("date_order", "warn", " ".join(i["title"] + "." for i in by_code["date_order"]), mask=mask_of("date_order"),
              cols=[c for c in d.columns if str(c).startswith("days_between_")][:2])
    else:
        R.put("date_order", "pass" if any(str(c).startswith("days_between_") for c in d.columns) else "n/a", "Later steps are never dated before earlier ones.", n=0)
    # 23 product conflicts: one code, several names, or prices that differ wildly
    if "product_id" in d.columns:
        notes, masks = [], []
        name_col = next((c for c in (F.groups.get("name_label") or []) if c in d.columns), None)
        if name_col:
            nn = d.groupby("product_id")[name_col].nunique()
            bad = nn[nn > 1].index
            if len(bad):
                notes.append(f"{len(bad):,} product code(s) appear with more than one name (e.g. {bad[0]})")
                masks.append(d["product_id"].isin(bad))
        if "unit_price" in d.columns:
            g = d[d["unit_price"] > 0].groupby("product_id")["unit_price"]
            spread = (g.max() / g.min()).replace([np.inf], np.nan)
            cnt = g.size()
            wild = spread[(spread >= 3) & (cnt >= 3)].index
            if len(wild):
                notes.append(f"{len(wild):,} product(s) sold at prices more than 3x apart (e.g. {wild[0]}: {g.min()[wild[0]]:g} to {g.max()[wild[0]]:g})")
                masks.append(d["product_id"].isin(wild))
        if masks:
            m = masks[0]
            for x in masks[1:]:
                m = m | x
            R.put("product_conflicts", "warn", "; ".join(notes) + ". Check whether codes were reused or prices mistyped.", mask=pd.Series(m.to_numpy(), index=R.df.index),
                  cols=[col("product_id")] + ([name_col] if name_col else []) + ([col("unit_price")] if "unit_price" in d.columns else []), flag_rows=False)
        else:
            R.put("product_conflicts", "pass", "Each product code has one name and consistent prices.", n=0)
    else:
        R.put("product_conflicts", "n/a", "No product code column.")


def _status(R: _Run, p):
    warns = [w for w in p.warnings if "although the order status says they count" in w]
    if warns:
        R.put("status_conflicts", "warn", " ".join(warns), n=0)
    elif any(i.get("role") == "category" and re.search(r"status|state|outcome", c, re.I) for c, i in p.roles.items()):
        R.put("status_conflicts", "pass", "Statuses agree with the other columns (cancelled or returned rows are not counted as sales).", n=0)
    else:
        R.put("status_conflicts", "n/a", "No status column.")


def _extremes(R: _Run, F):
    if F is None:
        R.put("extreme_values", "n/a", "No number columns."); return
    d = F.df
    found = False
    for k in ("revenue", "quantity", "unit_price", "cost", "profit"):
        if k not in d.columns:
            continue
        v = d[k].dropna()
        v = v[v > 0] if k != "profit" else v.abs()
        if len(v) < 50:
            continue
        med = float(v.median())
        mad = float((v - med).abs().median()) or (med * 0.1 or 1.0)
        thr = max(med + 25 * mad, float(v.quantile(0.999)) * 1.5, 20 * med)
        big = (d[k].abs() > thr).fillna(False) if k == "profit" else (d[k] > thr).fillna(False)
        if 0 < int(big.sum()) <= max(5, 0.002 * len(d)):
            found = True
            m = pd.Series(big.to_numpy(), index=R.df.index)
            share = float(d.loc[big, k].abs().sum() / max(d[k].abs().sum(), 1e-9))
            R.put("extreme_values", "warn", f"{int(big.sum()):,} row(s) with an unusually large {CONCEPTS[k].label.lower()} (over {thr:,.2f}, typical {med:,.2f}); together {share:.1%} "
                  f"of all {CONCEPTS[k].label.lower()}. A single entry like this can make a whole month look different.", mask=m, cols=[F.canon.get(k, k)])
        # a sudden change of scale (prices entered in paise, or thousands) from one month to the next
        if k in ("unit_price", "revenue") and "_t" in d.columns and d["_t"].notna().any():
            mon = d[d[k] > 0].groupby(d["_t"].dt.to_period("M"))[k].median()
            if len(mon) >= 4:
                ratio = (mon / mon.median())
                jump = ratio[(ratio >= 20) | (ratio <= 0.05)]
                if len(jump):
                    found = True
                    R.put("extreme_values", "warn", f"{CONCEPTS[k].label}: the typical value in {', '.join(str(x) for x in jump.index[:3])} is about {float(jump.iloc[0]):.0f}x the usual. "
                          "This often means a change of unit (paise vs rupees, units vs thousands).", n=0)
    if not found:
        R.put("extreme_values", "pass", "No single value or month is wildly out of scale.", n=0)


# ------------------------------------------------------------------------------------------------ across files
def _overlap(tables: dict) -> dict[str, dict]:
    out = {}
    names = [n for n, p in tables.items() if getattr(p, "kind", "") != "summary"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = tables[a].df, tables[b].df
            common = [c for c in A.columns if c in B.columns and not str(c).startswith("_")]
            if len(common) < max(3, 0.6 * min(A.shape[1], B.shape[1]) - 1):
                continue
            ha = pd.util.hash_pandas_object(A[common].astype(str), index=False)
            hb = pd.util.hash_pandas_object(B[common].astype(str), index=False)
            both = ha.isin(set(hb))
            if both.sum() >= max(5, 0.01 * len(A)):
                out[a] = {"other": b, "rows": int(both.sum()), "mask": both}
    return out


def _orphans(R: _Run, name: str, links: list, tables: dict):
    found = False
    for l in links or []:
        if getattr(l, "child", None) != name or not (getattr(l, "use", False) or getattr(l, "coverage", 0) >= 0.5):
            continue                                # a link that was rejected for low overlap is still worth reporting
        child, parent = tables[name].df, tables[l.parent].df
        if l.child_col not in child.columns or l.parent_col not in parent.columns:
            continue
        have = set(parent[l.parent_col].dropna().astype(str).str.strip())
        miss = child[l.child_col].notna() & ~child[l.child_col].astype(str).str.strip().isin(have)
        if miss.any():
            found = True
            R.put("orphan_codes", "warn", f"{int(miss.sum()):,} rows use a {l.child_col} that is not in {l.parent} ({miss.mean():.1%}). Details looked up from "
                  f"{l.parent} (cost, category...) are missing for them."
                  + ("" if getattr(l, "use", False) else f" Because of this the two files are not joined yet; confirm the link on 'How I read your files' to join them."),
                  mask=miss, cols=[l.child_col])
        else:
            found = True
            R.put("orphan_codes", "pass", f"Every {l.child_col} exists in {l.parent}.", n=0)
    if not found:
        R.put("orphan_codes", "n/a", "No linked list to check against.")


# ------------------------------------------------------------------------------------------------ main
def validate(tables: dict, frames: dict, model: dict, links: list | None = None) -> dict:
    """Run every check on every file. Returns the Data check section of the report, and leaves a per-row status column
    ('_status': ok | fixed | flagged | left out) and the failed checks ('_checks') on each frame."""
    files, extra_items = [], []
    overlap = _overlap(tables)
    for name, p in tables.items():
        if getattr(p, "kind", "") == "summary":
            continue
        fm = model["files"].get(name, {})
        concept_of = {c: v["concept"] for c, v in fm.get("columns", {}).items()}
        F = frames.get(name)
        d = p.df
        money = None
        rc = next((c for c, k in concept_of.items() if k == "revenue" and c in d.columns), None)
        if rc is not None:
            money = _num(d[rc])
        cur = getattr(F, "currency", None) if F is not None else None
        R = _Run(name, d, money, cur)
        info = _from_notes(R, p.notes)
        _structure(R, p)
        _missing(R, p, concept_of)
        _time(R, p)
        _duplicate_ids(R, p, concept_of, fm.get("file", {}))
        if name in overlap:
            o = overlap[name]
            R.put("overlapping_files", "warn", f"{o['rows']:,} rows also appear in {o['other']}. If both files are uploaded, those rows would count twice; "
                  "keep one of the files or remove the overlap.", mask=o["mask"], cols=[])
        else:
            R.put("overlapping_files", "pass" if len(tables) > 1 else "n/a", "No rows shared with another uploaded file." if len(tables) > 1 else "Only one file uploaded.", n=0)
        _text_in_numbers(R, p, concept_of)
        _dates(R, p, concept_of)
        _variants(R, p, info.get("case_merged", []))
        same_rows = F is not None and len(F.df) == len(d)
        _mixed_scales(R, p, concept_of)
        _rules(R, F if same_rows else None, cur, extra_items)
        _status(R, p)
        _extremes(R, F if same_rows else None)
        _orphans(R, name, links or [], tables)
        # row statuses
        ok = p.ok.reindex(d.index, fill_value=True).fillna(True).astype(bool) if p.ok is not None else pd.Series(True, index=d.index)
        status = pd.Series("ok", index=d.index, dtype=object)
        status[R.fixed] = "fixed"
        status[R.flag != ""] = "flagged"
        status[~ok] = "left out"
        if F is not None and same_rows:
            F.df["_status"] = status.to_numpy()
            F.df["_checks"] = R.flag.to_numpy()
        dropped = info["dropped_duplicates"] + info["dropped_totals"]
        counts = status.value_counts().to_dict()
        why_out = []
        if (~ok).any():
            why_out.append(f"{int((~ok).sum()):,} cancelled / returned / failed rows (kept in the file, not counted as sales)")
        if info["dropped_totals"]:
            why_out.append(f"{info['dropped_totals']} total row(s)")
        if info["dropped_duplicates"]:
            why_out.append(f"{info['dropped_duplicates']:,} exact copies")
        rec = None
        if money is not None:
            all_m, counted = float(money.sum()), float(money[ok].sum())
            rec = {"sales_in_file": all_m, "sales_counted": counted, "sales_left_out": all_m - counted,
                   "sales_on_flagged_rows": float(money[(status == "flagged")].sum())}
        results = [R.results[c] for c, _, _ in CHECKS if c in R.results]
        problems = [r for r in results if r["status"] in ("warn", "fail")]
        files.append({"file": name, "rows_in_file": int(len(d) + dropped), "rows_read": int(len(d)),
                      "rows": {"ok": int(counts.get("ok", 0)), "fixed": int(counts.get("fixed", 0)), "flagged": int(counts.get("flagged", 0)),
                               "left_out": int(counts.get("left out", 0)) + dropped},
                      "left_out_because": why_out, "reconciliation": rec, "checks": results,
                      "problems": len(problems), "serious": sum(1 for r in problems if r["status"] == "fail")})
    tot = {k: sum(f["rows"][k] for f in files) for k in ("ok", "fixed", "flagged", "left_out")}
    rows_in = sum(f["rows_in_file"] for f in files)
    headline = (f"{rows_in:,} rows: {tot['ok']:,} fine, {tot['fixed']:,} cleaned, {tot['flagged']:,} flagged, {tot['left_out']:,} left out."
                if files else "No files to check.")
    return {"headline": headline, "rows_in": rows_in, "rows": tot, "files": files,
            "checks_total": len(CHECKS), "groups": list(dict.fromkeys(g for _, g, _ in CHECKS)), "items": extra_items}

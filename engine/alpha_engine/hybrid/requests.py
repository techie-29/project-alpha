"""The order form: how the AI asks for a calculation without writing code, and the code that checks and runs it.

A request (JSON):
  {"id": "q1", "question": "...", "why": "...", "file": "<file name, optional>",
   "measure": {"metric": "<catalogue metric id>"}                      # a named metric, e.g. margin, loss_line_share
           or {"op": "<op>", "col": "<column>", "den": "<column, ratio only>"},
   "by": [ up to 2 of: "<group column>" | {"time": "year|quarter|month|week|weekday"} | {"col": "<number column>", "bins": [edges]} ],
   "filter": [ {"col": "<column or 'date'>", "op": "== != > < >= <= in not_in >col <col", "value": ...} ],
   "sort": "desc|asc", "top": 1-25}
ops: sum, mean, median, min, max, count, count_distinct, ratio (sum(col) / sum(den)), share_negative (share of rows with col < 0),
     share (share of all rows that pass the filter - e.g. how many lines lose money).

Every result says which rows it used, the formula in words, and keeps a sample of the source rows (with their row
number in the file) so the owner can check it. Same request, same answer, every time."""
from __future__ import annotations
import numpy as np
import pandas as pd
from ..metrics.catalogue import BY_ID, _agg, _latest, _items, _mask

OPS = {"sum", "mean", "median", "min", "max", "count", "count_distinct", "ratio", "share_negative", "share"}
FOPS = {"==", "!=", ">", "<", ">=", "<=", "in", "not_in", ">col", "<col"}
GRAINS = {"year": "Y", "quarter": "Q", "month": "M", "week": "W-SUN", "weekday": None}
MAX_GROUPS = 25
EVIDENCE_ROWS = 15

GRAMMAR = """A request is one JSON object:
{"id": "q1", "question": "plain question", "why": "why it matters for THIS business", "file": "<file name; optional, default the main sales file>",
 "measure": {"metric": "<id from metrics.available>"}  OR  {"op": "<op>", "col": "<column>", "den": "<column, only for ratio>"},
 "by": [ up to 2 of: "<column from groups_to_split_by>" | {"time": "year|quarter|month|week|weekday"} | {"col": "<number column>", "bins": [edges]} ],
 "filter": [ {"col": "<column, or 'date'>", "op": "== != > < >= <= in not_in >col <col", "value": <value; a list for in/not_in; another column for >col/<col; 'YYYY-MM-DD' for date>} ],
 "sort": "desc|asc", "top": <1-25>}
ops: sum, mean, median, min, max, count (rows), count_distinct (of col), ratio (sum(col) / sum(den), e.g. profit / revenue),
share_negative (share of rows where col < 0), share (share of rows that pass the filter, out of all rows).
Use column names exactly as given (use_as when present, else name). 'by' may be empty for one overall number.
Only rows that count are used (cancelled / returned rows are left out). Compare a column with another in a filter, e.g. {"col":"profit","op":">col","value":"revenue"}."""


class Bad(ValueError):
    pass


def _cols(F) -> set[str]:
    return {c for c in F.df.columns if not str(c).startswith("_")}


def _num(d, c):
    if c not in d.columns or not pd.api.types.is_numeric_dtype(d[c]):
        raise Bad(f"'{c}' is not a number column")
    return d[c]


def _base(F, money: bool) -> pd.DataFrame:
    d = F.df[F.df["_ok"].astype(bool)] if "_ok" in F.df.columns else F.df
    if money and "_cur" in d.columns and F.currency:
        d = d[d["_cur"] == F.currency]
    return d


def _filter(F, d: pd.DataFrame, flt: list) -> tuple[pd.DataFrame, list[str]]:
    cols, words = _cols(F), []
    for f in flt or []:
        if not isinstance(f, dict):
            raise Bad("a filter must be an object")
        c, fo, v = f.get("col"), f.get("op"), f.get("value")
        if fo not in FOPS:
            raise Bad(f"unknown filter op '{fo}'")
        if c == "date":
            if "_t" not in d.columns:
                raise Bad("this file has no dates")
            try:
                ts = pd.Timestamp(str(v))
            except Exception:
                raise Bad(f"bad date '{v}'")
            s = d["_t"]
            mask = {"==": s.dt.normalize() == ts, "!=": s.dt.normalize() != ts, ">": s > ts, "<": s < ts, ">=": s >= ts, "<=": s <= ts}.get(fo)
            if mask is None:
                raise Bad("dates take == != > < >= <=")
            d = d[mask.fillna(False)]; words.append(f"date {fo} {ts.date()}")
            continue
        if c not in cols:
            raise Bad(f"unknown column '{c}'")
        s = d[c]
        if fo in (">col", "<col"):
            if v not in cols:
                raise Bad(f"unknown column '{v}'")
            mask = (_num(d, c) > _num(d, v)) if fo == ">col" else (_num(d, c) < _num(d, v))
            words.append(f"{c} {'>' if fo == '>col' else '<'} {v}")
        elif fo in ("in", "not_in"):
            vals = [str(x) for x in (v if isinstance(v, list) else [v])]
            mask = s.astype(str).isin(vals)
            mask = mask if fo == "in" else ~mask
            words.append(f"{c} {'in' if fo == 'in' else 'not in'} {', '.join(vals[:5])}")
        else:
            if pd.api.types.is_numeric_dtype(s):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise Bad(f"filter value {v!r} is not a number")
            else:
                s, v = s.astype(str), str(v)
            mask = {"==": s == v, "!=": s != v, ">": s > v, "<": s < v, ">=": s >= v, "<=": s <= v}[fo]
            words.append(f"{c} {fo} {v}")
        d = d[mask.fillna(False)]
    return d, words


def _keys(F, d: pd.DataFrame, by: list) -> tuple[list, list[str]]:
    cols, keys, names = _cols(F), [], []
    for b in (by or [])[:2]:
        if isinstance(b, str):
            if b not in cols:
                raise Bad(f"unknown column '{b}'")
            keys.append(d[b].astype("string").fillna("(blank)")); names.append(b)
        elif isinstance(b, dict) and b.get("time") in GRAINS:
            if "_t" not in d.columns:
                raise Bad("this file has no dates")
            g = b["time"]
            k = d["_t"].dt.day_name() if g == "weekday" else d["_t"].dt.to_period(GRAINS[g]).astype(str)
            keys.append(k); names.append(g)
        elif isinstance(b, dict) and b.get("col") in cols and isinstance(b.get("bins"), list) and len(b["bins"]) >= 2:
            try:
                edges = sorted({float(x) for x in b["bins"]})
            except (TypeError, ValueError):
                raise Bad("bins must be numbers")
            if len(edges) < 2:
                raise Bad("bins need two different edges")
            keys.append(pd.cut(_num(d, b["col"]), edges, include_lowest=True).astype(str)); names.append(f"{b['col']} band")
        else:
            raise Bad(f"bad 'by' item {b}")
    return keys, names


def _measure(F, m: dict):
    """Returns (function(rows) -> number, words, columns used, money?)."""
    if not isinstance(m, dict):
        raise Bad("measure must be an object")
    if m.get("metric"):
        mid = m["metric"]
        if mid not in BY_ID:
            raise Bad(f"unknown metric '{mid}'")
        M = BY_ID[mid]
        if not all(F.has(n) for n in M.needs) or F.role not in M.roles:
            raise Bad(f"metric '{mid}' cannot be calculated from this file")
        items = _items(F, F.df)

        def fn(x, M=M):
            if M.spec[0] in ("latest_level", "latest_count_if"):
                return float(_latest(x, M.spec, None, items)) if len(x) else np.nan
            v = _agg(x, M.spec, None)
            return float(v) if v is not None and np.isfinite(v) else np.nan
        used = [n for n in M.needs if n in F.df.columns]
        return fn, f"{M.label} ({M.how})", used, M.money
    op, col, den = m.get("op"), m.get("col"), m.get("den")
    if op not in OPS:
        raise Bad(f"unknown op '{op}'")
    cols = _cols(F)
    if op not in ("count", "share") and col not in cols:
        raise Bad(f"unknown column '{col}'")
    if op == "ratio" and den not in cols:
        raise Bad(f"unknown column '{den}'")
    if op in ("sum", "mean", "median", "min", "max", "ratio", "share_negative"):
        _num(F.df, col)
    if op == "ratio":
        _num(F.df, den)
    money = col in ("revenue", "gross_revenue", "profit", "cost", "expense", "discount", "tax", "unit_price", "unit_cost")

    def fn(x):
        if op == "count":
            return float(len(x))
        if op == "share":
            return np.nan                                    # filled in by run(): rows passing the filter / all rows of the group
        if op == "count_distinct":
            return float(x[col].nunique())
        s = x[col]
        if op == "ratio":
            dd = x[den].sum()
            return float(s.sum() / dd) if dd else np.nan
        if op == "share_negative":
            s = s.dropna()
            return float((s < 0).mean()) if len(s) else np.nan
        v = getattr(s, op)()
        return float(v) if v is not None and np.isfinite(v) else np.nan
    words = {"sum": f"total of {col}", "mean": f"average {col}", "median": f"median {col}", "min": f"smallest {col}", "max": f"largest {col}",
             "count": "number of rows", "count_distinct": f"number of different {col}", "ratio": f"sum of {col} / sum of {den}",
             "share_negative": f"share of rows where {col} is below zero", "share": "share of rows that pass the filter"}[op]
    return fn, words, [c for c in (col, den) if c], money


def _clean(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return float(round(float(v), 6))


def run(F, rq: dict) -> dict:
    if not isinstance(rq, dict):
        raise Bad("request is not an object")
    fn, words, used, money = _measure(F, rq.get("measure") or {})
    base = _base(F, money)
    d, fwords = _filter(F, base, rq.get("filter"))
    share = (rq.get("measure") or {}).get("op") == "share"
    keys, names = _keys(F, d, rq.get("by"))
    out = {"rows_used": int(len(d)), "formula": words + (f", rows where {' and '.join(fwords)}" if fwords else "") + (f", split by {' and '.join(names)}" if names else "")}
    if share:
        out["overall"] = _clean(len(d) / len(base)) if len(base) else None
    else:
        out["overall"] = _clean(fn(d)) if len(d) else None
    if keys:
        if share:
            bk, _ = _keys(F, base, rq.get("by"))
            tot = base.groupby(bk, observed=True).size()
            got = d.groupby(keys, observed=True).size()
            vals = (got / tot.reindex(got.index)).to_dict()
            sizes = got.to_dict()
        else:
            g = d.groupby(keys, observed=True)
            vals = {k: fn(x) for k, x in g}
            sizes = g.size().to_dict()
        rows = [{"group": " | ".join(map(str, k)) if isinstance(k, tuple) else str(k), "value": _clean(v), "rows": int(sizes.get(k, 0))} for k, v in vals.items()]
        time_like = any(n in GRAINS for n in names)
        if time_like and len(names) == 1:
            rows.sort(key=lambda r: r["group"])
        else:
            asc = rq.get("sort") == "asc"
            rows.sort(key=lambda r: (r["value"] is None, (r["value"] or 0) if asc else -(r["value"] or 0)))
        try:
            top = max(1, min(int(rq.get("top") or MAX_GROUPS), MAX_GROUPS))
        except (TypeError, ValueError):
            top = MAX_GROUPS
        out["groups"] = len(rows)
        out["rows"] = rows if (time_like and len(rows) <= 60) else rows[:top]
        out["by"] = names
    # source rows behind the number (biggest first), so the owner can check it
    show = [c for c in dict.fromkeys(["_row"] + [n for n in (rq.get("by") or []) if isinstance(n, str)] + used + [f.get("col") for f in rq.get("filter") or [] if isinstance(f, dict)])
            if c in d.columns]
    if "_t" in d.columns:
        show.insert(1, "_t")
    sort_col = next((c for c in used if c in d.columns and pd.api.types.is_numeric_dtype(d[c])), None)
    sample = d.reindex(d[sort_col].abs().sort_values(ascending=False).index) if sort_col else d
    sample = sample[show].head(EVIDENCE_ROWS)
    out["evidence"] = {"columns": ["Row in file" if c == "_row" else ("date" if c == "_t" else (F.canon.get(c, c) if isinstance(F.canon.get(c), str) else c)) for c in show],
                       "rows": sample.astype(object).where(sample.notna(), None).map(lambda x: x.isoformat()[:10] if isinstance(x, pd.Timestamp) else x).values.tolist(),
                       "total": int(len(d))}
    return out


def run_all(frames: dict, main: str | None, requests: list, done: dict | None = None) -> dict:
    """Run every request; returns {id: {"ok", "request", "result" | "error", "rows_used"}}."""
    done = {} if done is None else done
    for i, rq in enumerate(requests or []):
        rid = str((rq or {}).get("id") or f"r{len(done) + 1}") if isinstance(rq, dict) else f"r{len(done) + 1}"
        if rid in done:
            rid = f"{rid}_{len(done) + 1}"
        try:
            fname = (rq or {}).get("file") if isinstance(rq, dict) else None
            F = frames.get(fname) if fname in frames else frames.get(main) if main in frames else next(iter(frames.values()))
            res = run(F, rq)
            done[rid] = {"ok": True, "request": rq, "file": F.name, "result": res, "rows_used": res["rows_used"]}
        except Bad as e:
            done[rid] = {"ok": False, "request": rq, "error": str(e)}
        except Exception as e:                                       # a bug here must not stop the report
            done[rid] = {"ok": False, "request": rq, "error": f"could not run: {type(e).__name__}: {str(e)[:120]}"}
    return done


def compact(done: dict) -> list[dict]:
    """What the AI sees of the results: the numbers, not the source rows."""
    out = []
    for rid, r in done.items():
        if r["ok"]:
            res = {k: v for k, v in r["result"].items() if k != "evidence"}
            out.append({"id": rid, "question": (r["request"] or {}).get("question"), "file": r.get("file"), "result": res})
        else:
            out.append({"id": rid, "question": (r["request"] or {}).get("question") if isinstance(r["request"], dict) else None, "error": r["error"]})
    return out

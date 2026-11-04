"""Model test bench: how well does an AI model plan an analysis and write it up, on one of your files?

It runs on your own computer with your OpenRouter key (engine/.env). For each model it does what the new design would ask
the AI to do, and scores it:

  1. PLAN   - the model gets a privacy-safe profile of the data (column names, meanings, statistics, a few category
              values; never raw rows) and returns a plan: data checks plus 12-20 questions, each as a small structured
              request ("margin = profit / sales, by year"). It writes no code.
  2. RUN    - this script checks every request against a fixed grammar and calculates it with pandas. Same request,
              same answer, every time.
  3. WRITE  - the model gets the exact results and writes structured findings (headline, points with numbers, why it
              matters, what to look into, which chart). Every number it writes is checked against the results.
  4. ASK    - two Ask Alpha questions, answered the same way (plan -> run -> structured answer).

Usage (from the engine folder, virtual environment active):
    python model_bench.py INDIA_RETAIL_DATA.xlsx
    python model_bench.py INDIA_RETAIL_DATA.xlsx --models deepseek/deepseek-chat other/model-id
    python model_bench.py INDIA_RETAIL_DATA.xlsx --fake            (no AI at all; checks the bench itself)

Output: ./alpha_bench/<time>/summary.md, plus one JSON per model with everything the model said and every result.
Send the whole folder back for review.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
_env = ENGINE / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from alpha_engine import pipeline                              # noqa: E402
from alpha_engine.llm import parse_json_text                   # noqa: E402
from alpha_engine.investigate.ai import describe_frames        # noqa: E402
from alpha_engine.investigate.verifier import verify           # noqa: E402

OPS = {"sum", "mean", "median", "min", "max", "count", "count_distinct", "ratio", "share_negative"}
FOPS = {"==", "!=", ">", "<", ">=", "<=", "in", "not_in", ">col", "<col"}
GRAINS = {"year", "quarter", "month", "weekday"}
MAX_ROWS_BACK = 25

# ---------------------------------------------------------------- the grammar the model must follow
GRAMMAR = """A request is one JSON object:
{"id": "q1", "question": "plain question", "why": "why it is worth asking for THIS business",
 "measure": {"op": "<op>", "col": "<column>", "den": "<column, only for ratio>"},
 "by": [ up to 2 items, each one of: "<category column>" | {"time": "year|quarter|month|weekday"} | {"col": "<numeric column>", "bins": [edges]} ],
 "filter": [ {"col": "<column>", "op": "== != > < >= <= in not_in >col <col", "value": <value, list for in/not_in, or another column name for >col/<col>} ],
 "sort": "desc|asc", "top": <1-25>}
ops: sum, mean, median, min, max, count (rows), count_distinct (of col), ratio (sum(col)/sum(den), e.g. margin = profit/revenue),
share_negative (share of rows where col < 0).
'by' may be empty for one overall number. Only use column names that appear in the profile. Only rows that count
(not cancelled/returned) are used. You may compare one column with another in a filter, e.g. {"col":"profit","op":">col","value":"revenue"}."""

PLAN_SYSTEM = ("You are a senior business analyst. You get a privacy-safe profile of a business's data (no raw rows) and some "
               "headline numbers. Plan the analysis an expert would run on THIS data to find what the owner most needs to know: "
               "problems, risks, opportunities, changes over time, things that look wrong in the data. Avoid obvious facts that are "
               "true of every business (a few customers buy most; expensive products have bigger sales) and avoid splits that only "
               "restate a price list. Reply only with JSON: "
               '{"understanding": "2-3 sentences: what this business is and what the data can and cannot show", '
               '"data_checks": [requests that test whether the data itself is trustworthy], '
               '"questions": [12 to 20 requests, most important first]}.\n' + GRAMMAR)

WRITE_SYSTEM = ("You are a senior business analyst writing for a busy owner. You get the requests that were run and their exact "
                "results. Write only findings the results support. Use only numbers that appear in the results (you may round). "
                "Never claim that one thing caused another; say what lines up with what and what the data cannot tell. Lead with "
                "what matters most (money, risk, trend), skip obvious or weak results, and flag data that looks wrong. "
                "Reply only with JSON: {\"headline\": \"one sentence\", \"findings\": [{\"title\": \"specific, with the key number\", "
                "\"points\": [\"2-4 short points, each with a number\"], \"why_it_matters\": \"one sentence\", "
                "\"look_into\": \"one concrete next check\", \"evidence\": [\"request ids\"], "
                "\"chart\": {\"type\": \"bar|line|table|none\", \"request\": \"request id\"}, \"importance\": \"high|medium|low\"}], "
                "\"data_warnings\": [\"plain sentences\"]}. 5 to 10 findings.")

ASK_PLAN_SYSTEM = ("You answer a business owner's question about their own data. Plan 1 to 6 requests that answer it. Reply only "
                   "with JSON: {\"requests\": [ ... ]}.\n" + GRAMMAR)

ASK_ANSWER_SYSTEM = ("Answer the owner's question from the results below. Use only numbers in the results; never claim a cause. "
                     "Reply only with JSON: {\"short_answer\": \"one sentence\", \"key_points\": [\"3-6 points, each with a number\"], "
                     "\"how_worked_out\": [\"one line per request used\"], \"what_it_means\": \"1-2 sentences\", "
                     "\"cannot_tell\": \"what the data cannot show\"}.")

ASK_QUESTIONS = ["How is the business doing on profit?",
                 "What were the least selling items this year compared with last year?"]


# ---------------------------------------------------------------- loading the file with the engine (no AI)
def load(path: str):
    d = tempfile.mkdtemp(prefix="alpha_bench_")
    name = Path(path).name
    rep = pipeline.analyze("bench", [{"name": name, "path": str(Path(path).resolve())}], {}, d, None)
    frames = pipeline.load_state(Path(d) / "analyses" / "bench" / "state.pkl.gz")
    return rep, frames


def profile(rep: dict, frames: dict) -> dict:
    tabs = describe_frames(frames)
    for (fname, F), t in zip(frames.items(), tabs):   # the bench works on the main table; say which columns are usable
        t["columns"] = [c for c in t["columns"] if not c["name"].startswith("_")]
        for c in t["columns"]:                       # show the file's own header next to the engine's label
            if c["name"] in F.canon and F.canon[c["name"]] != c["name"]:
                c["header_in_file"] = F.canon[c["name"]]
    tiles = [{"label": t["label"], "value": t["value"], "unit": t.get("unit")} for t in rep["overview"]["tiles"]]
    return {"tables": tabs, "headline_numbers": tiles, "date_range": rep["briefing"].get("coverage")}


# ---------------------------------------------------------------- the deterministic executor
class Bad(ValueError):
    pass


def _cols(df) -> set[str]:
    return {c for c in df.columns if not c.startswith("_")}


def _num(df, c):
    if c not in df.columns or not pd.api.types.is_numeric_dtype(df[c]):
        raise Bad(f"'{c}' is not a numeric column")
    return df[c]


def run_request(df: pd.DataFrame, rq: dict) -> dict:
    if not isinstance(rq, dict):
        raise Bad("request is not an object")
    cols = _cols(df)
    m = rq.get("measure") or {}
    op, col, den = m.get("op"), m.get("col"), m.get("den")
    if op not in OPS:
        raise Bad(f"unknown op '{op}'")
    d = df[df["_ok"].astype(bool)] if "_ok" in df.columns else df
    for f in rq.get("filter") or []:
        c, fo, v = f.get("col"), f.get("op"), f.get("value")
        if c not in cols or fo not in FOPS:
            raise Bad(f"bad filter {f}")
        s = d[c]
        if fo in (">col", "<col"):
            if v not in cols:
                raise Bad(f"bad column in filter {v}")
            mask = (_num(d, c) > _num(d, v)) if fo == ">col" else (_num(d, c) < _num(d, v))
        elif fo in ("in", "not_in"):
            vals = [str(x) for x in (v if isinstance(v, list) else [v])]
            mask = s.astype(str).isin(vals)
            mask = mask if fo == "in" else ~mask
        else:
            if pd.api.types.is_numeric_dtype(s):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise Bad(f"filter value {v!r} is not a number")
            else:
                s, v = s.astype(str), str(v)
            mask = {"==": s == v, "!=": s != v, ">": s > v, "<": s < v, ">=": s >= v, "<=": s <= v}[fo]
        d = d[mask.fillna(False)]
    keys, names = [], []
    for b in (rq.get("by") or [])[:2]:
        if isinstance(b, str):
            if b not in cols:
                raise Bad(f"unknown column '{b}'")
            keys.append(d[b].astype(str)); names.append(b)
        elif isinstance(b, dict) and b.get("time") in GRAINS:
            t = d["_t"]
            g = b["time"]
            k = {"year": t.dt.year.astype("Int64").astype(str), "quarter": t.dt.to_period("Q").astype(str),
                 "month": t.dt.to_period("M").astype(str), "weekday": t.dt.day_name()}[g]
            keys.append(k); names.append(g)
        elif isinstance(b, dict) and b.get("col") in cols and isinstance(b.get("bins"), list) and len(b["bins"]) >= 2:
            edges = sorted({float(x) for x in b["bins"]})
            keys.append(pd.cut(_num(d, b["col"]), edges, include_lowest=True).astype(str)); names.append(b["col"] + " band")
        else:
            raise Bad(f"bad 'by' item {b}")

    def value(x: pd.DataFrame) -> float:
        if op == "count":
            return float(len(x))
        if op == "count_distinct":
            if col not in cols:
                raise Bad(f"unknown column '{col}'")
            return float(x[col].nunique())
        s = _num(x, col)
        if op == "ratio":
            dd = _num(x, den).sum()
            return float(s.sum() / dd) if dd else float("nan")
        if op == "share_negative":
            return float((s < 0).mean()) if len(s) else float("nan")
        return float(getattr(s, op)())

    out = {"rows_used": int(len(d)), "overall": _clean(value(d)) if len(d) else None}
    if keys:
        g = d.groupby(keys, observed=True)
        rows = [{"group": " | ".join(map(str, k if isinstance(k, tuple) else (k,))), "value": _clean(value(x)), "rows": int(len(x))} for k, x in g]
        time_like = any(n in GRAINS for n in names)
        if time_like and len(names) == 1:
            rows.sort(key=lambda r: r["group"])
        else:
            rows.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0) if rq.get("sort", "desc") != "asc" else (r["value"] or 0)))
        top = max(1, min(int(rq.get("top") or MAX_ROWS_BACK), MAX_ROWS_BACK))
        out["groups"] = len(rows)
        out["rows"] = rows if time_like else rows[:top]
        out["by"] = names
    return out


def _clean(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return float(round(v, 6))


def run_all(df, requests: list) -> list[dict]:
    done = []
    for i, rq in enumerate(requests or []):
        rid = str((rq or {}).get("id") or f"r{i + 1}") if isinstance(rq, dict) else f"r{i + 1}"
        try:
            res = run_request(df, rq)
            done.append({"id": rid, "request": rq, "ok": True, "result": res})
        except Bad as e:
            done.append({"id": rid, "request": rq, "ok": False, "error": str(e)})
        except Exception as e:                                     # a bug in the bench, not the model
            done.append({"id": rid, "request": rq, "ok": False, "error": f"bench error {type(e).__name__}: {e}"})
    return done


# ---------------------------------------------------------------- talking to OpenRouter (with timing and cost)
class Client:
    def __init__(self, model: str):
        self.model, self.key = model, os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.log = []
        if not self.key:
            raise SystemExit("OPENROUTER_API_KEY is not set in engine/.env")

    def ask(self, system: str, payload: dict) -> dict:
        body = json.dumps({"model": self.model, "temperature": 0.2, "max_tokens": 8192, "usage": {"include": True},
                           "response_format": {"type": "json_object"},
                           "messages": [{"role": "system", "content": system + "\nReply with one JSON object only."},
                                        {"role": "user", "content": json.dumps(payload, default=str)}]}).encode()
        t0, err = time.time(), None
        for attempt in range(3):
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.key}", "X-Title": "Project Alpha bench"})
            try:
                with urllib.request.urlopen(req, timeout=240) as r:
                    data = json.load(r)
                if data.get("error"):
                    err = str(data["error"])[:200]; time.sleep(4 * (attempt + 1)); continue
                text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                u = data.get("usage") or {}
                self.log.append({"seconds": round(time.time() - t0, 1), "in": u.get("prompt_tokens"), "out": u.get("completion_tokens"), "cost": u.get("cost")})
                try:
                    return parse_json_text(text)
                except Exception:
                    self.log[-1]["bad_json"] = True
                    return {"_unreadable": text[:2000]}
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}"
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(5 * (attempt + 1)); continue
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"; time.sleep(3)
        self.log.append({"seconds": round(time.time() - t0, 1), "error": err})
        return {"_error": err}


class FakeClient:
    """No AI: a fixed, reasonable plan, so the bench itself can be checked without a key."""
    model = "fake (no AI)"

    def __init__(self, cols: dict):
        self.log, self.c = [], cols

    def ask(self, system: str, payload: dict) -> dict:
        self.log.append({"seconds": 0})
        if system is PLAN_SYSTEM:
            R = lambda i, q, m, by=(), f=(), **k: {"id": i, "question": q, "why": "-", "measure": m, "by": list(by), "filter": list(f), **k}
            ratio = {"op": "ratio", "col": "profit", "den": "revenue"}
            return {"understanding": "fake", "data_checks": [
                R("d1", "Rows where profit is larger than the sale", {"op": "count"}, f=[{"col": "profit", "op": ">col", "value": "revenue"}])],
                "questions": [R("q1", "Margin by year", ratio, [{"time": "year"}]),
                              R("q2", "Share of loss-making sales", {"op": "share_negative", "col": "profit"}),
                              R("q3", "Margin by sub-category", ratio, ["Product Sub-Category"], top=8, sort="asc"),
                              R("q4", "Margin by discount band", ratio, [{"col": self.c.get("discount", "discount_pct"), "bins": [0, 0.05, 1]}]),
                              R("q5", "Margin by freight mode", ratio, ["Freight Mode"]),
                              R("q6", "Largest single sale per month", {"op": "max", "col": "revenue"}, [{"time": "month"}]),
                              R("q7", "bad request", {"op": "explode", "col": "nothing"})]}
        if system is ASK_PLAN_SYSTEM:
            return {"requests": [{"id": "a1", "measure": {"op": "ratio", "col": "profit", "den": "revenue"}, "by": [{"time": "year"}]}]}
        if system is ASK_ANSWER_SYSTEM:
            return {"short_answer": "fake", "key_points": [], "how_worked_out": [], "what_it_means": "", "cannot_tell": ""}
        return {"headline": "fake", "findings": [], "data_warnings": []}


# ---------------------------------------------------------------- checking what the model wrote
def check_text(obj, produced) -> list[dict]:
    """Every text field the model wrote, with the verifier's verdict."""
    out = []

    def walk(o, path):
        if isinstance(o, str):
            if o.strip() and path.split(".")[-1] not in ("type", "request", "importance") and not re.fullmatch(r"[a-z]\w*\d*", o):
                ok, why = verify(o, *produced)
                out.append({"field": path, "text": o, "ok": ok, "why": "" if ok else why})
        elif isinstance(o, dict):
            for k, v in o.items():
                if k != "evidence":
                    walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(obj, "")
    return out


def check_findings(written, results: list[dict], headline) -> list[dict]:
    """Stricter check: each finding's numbers must come from the results IT cites (its 'evidence' ids), not from anywhere.
    The engine's own checker only asks whether a similar number exists somewhere, which lets most invented percentages through."""
    by_id = {r["id"]: r for r in results}
    out = []
    if not isinstance(written, dict):
        return out
    out += check_text({"headline": written.get("headline")}, [results, headline])
    for i, f in enumerate(written.get("findings") or []):
        if not isinstance(f, dict):
            continue
        ev = [by_id[e] for e in (f.get("evidence") or []) if isinstance(e, str) and e in by_id]
        src = [ev, headline] if ev else [[]]
        for c in check_text({k: f.get(k) for k in ("title", "points", "why_it_matters", "look_into")}, src):
            c["field"] = f"findings[{i}].{c['field']}"
            if not ev:
                c["ok"], c["why"] = False, "no valid evidence id cited"
            out.append(c)
    out += check_text({"data_warnings": written.get("data_warnings")}, [results, headline])
    return out


# Known facts in INDIA_RETAIL_DATA.xlsx, checked by hand against the original file (Nov 2026).
INDIA_KEY = {
    "impossible_profit": "205 rows have profit larger than the sale (67% of all profit)",
    "margin_trend": "margin fell to 6.2% in 2013 from 12-16% before, while sales grew",
    "loss_share": "49% of sales lines lose money",
    "thin_big_sellers": "Sliced Pineapple (top seller) earns 1.4%; Jams -0.8%",
    "discount_margin": "discounts above 5% halve the margin (14.2% vs 7.3%)",
    "freight_margin": "Delivery Truck margin 6.8% vs 13.9-21.2% for air",
    "spike_one_order": "Nov 2012 spike is mostly one order of 100,119",
}


def score_india(plan_runs: list[dict], written: dict, cols: dict) -> dict:
    def has(pred):
        return any(r["ok"] and pred(r["request"]) for r in plan_runs)

    def m(rq):
        return rq.get("measure") or {}

    def by_names(rq):
        return [b if isinstance(b, str) else (b.get("time") or b.get("col")) for b in rq.get("by") or [] if isinstance(b, (str, dict))]

    is_margin = lambda rq: m(rq).get("op") == "ratio" and m(rq).get("col") == "profit" and m(rq).get("den") == "revenue"
    text = json.dumps(written, ensure_ascii=False).lower()
    hits = {
        "impossible_profit": has(lambda rq: any(f.get("op") in (">col", "<col") and {f.get("col"), f.get("value")} == {"profit", "revenue"} for f in rq.get("filter") or []))
                             or ("profit" in text and any(w in text for w in ("exceeds", "larger than the sale", "more than the sale", "greater than sales", "higher than sales"))),
        "margin_trend": has(lambda rq: is_margin(rq) and any(n in ("year", "quarter", "month") for n in by_names(rq))),
        "loss_share": has(lambda rq: m(rq).get("op") == "share_negative" and m(rq).get("col") == "profit")
                      or has(lambda rq: any(f.get("col") == "profit" and f.get("op") in ("<", "<=") for f in rq.get("filter") or [])),
        "thin_big_sellers": has(lambda rq: is_margin(rq) and "Product Sub-Category" in by_names(rq)),
        "discount_margin": has(lambda rq: cols.get("discount", "discount_pct") in by_names(rq) and (is_margin(rq) or m(rq).get("col") == "profit")),
        "freight_margin": has(lambda rq: is_margin(rq) and "Freight Mode" in by_names(rq)),
        "spike_one_order": has(lambda rq: m(rq).get("op") == "max" and m(rq).get("col") == "revenue"),
    }
    reported = {
        "margin_trend": "2013" in text and "margin" in text,
        "thin_big_sellers": "sliced pineapple" in text or "jams" in text,
        "loss_share": "loss" in text,
        "impossible_profit": hits["impossible_profit"] and ("data" in text and "profit" in text),
    }
    return {"looked_for": hits, "mentioned_in_writeup": reported, "found": sum(hits.values()), "of": len(hits)}


# ---------------------------------------------------------------- one model, end to end
def bench_model(client, prof: dict, df: pd.DataFrame, india: bool, cols: dict) -> dict:
    r = {"model": client.model}
    plan = client.ask(PLAN_SYSTEM, prof)
    r["plan"] = plan
    reqs = (plan.get("data_checks") or []) + (plan.get("questions") or []) if isinstance(plan, dict) else []
    runs = run_all(df, reqs)
    r["runs"] = runs
    good = [x for x in runs if x["ok"]]
    results = [{"id": x["id"], "question": (x["request"] or {}).get("question"), "request": x["request"], "result": x["result"]} for x in good]
    written = client.ask(WRITE_SYSTEM, {"understanding": plan.get("understanding") if isinstance(plan, dict) else None,
                                        "headline_numbers": prof["headline_numbers"], "results": results})
    r["written"] = written
    produced = [results, prof["headline_numbers"]]
    r["text_checks"] = check_findings(written, results, prof["headline_numbers"])
    r["ask"] = []
    for q in ASK_QUESTIONS:
        ap = client.ask(ASK_PLAN_SYSTEM, {"question": q, "profile": prof})
        ar = run_all(df, ap.get("requests") if isinstance(ap, dict) else [])
        res = [{"id": x["id"], "request": x["request"], "result": x["result"]} for x in ar if x["ok"]]
        ans = client.ask(ASK_ANSWER_SYSTEM, {"question": q, "results": res})
        r["ask"].append({"question": q, "plan": ap, "runs": ar, "answer": ans, "text_checks": check_text(ans, [res])})
    tc = r["text_checks"] + [c for a in r["ask"] for c in a["text_checks"]]
    findings = written.get("findings") if isinstance(written, dict) else None
    r["score"] = {
        "requests_planned": len(reqs),
        "requests_valid": len(good),
        "valid_share": round(len(good) / len(reqs), 2) if reqs else 0,
        "findings_written": len(findings) if isinstance(findings, list) else 0,
        "text_fields": len(tc),
        "text_fields_verified": sum(1 for c in tc if c["ok"]),
        "rejected_examples": [f"{c['field']}: {c['why']} :: {c['text'][:140]}" for c in tc if not c["ok"]][:8],
        "ask_answers_complete": sum(1 for a in r["ask"] if isinstance(a["answer"], dict) and a["answer"].get("short_answer") and a["answer"].get("key_points")),
        "seconds": round(sum(x.get("seconds", 0) for x in client.log), 1),
        "cost_usd": round(sum(x.get("cost") or 0 for x in client.log), 4),
        "calls": len(client.log),
        "call_errors": [x.get("error") for x in client.log if x.get("error")][:3],
        "bad_json": sum(1 for x in client.log if x.get("bad_json")),
    }
    if india:
        r["score"]["answer_key"] = score_india(runs, written, cols)
    return r


def summary_md(file: str, out: list[dict], india: bool) -> str:
    L = [f"# Model bench: {file}", "", f"Run {time.strftime('%Y-%m-%d %H:%M')}", "",
         "| Model | Valid requests | Findings | Numbers verified | Ask answers | Answer key | Time (s) | Cost (USD) |", "|---|---|---|---|---|---|---|---|"]
    for r in out:
        s = r["score"]
        ak = f"{s['answer_key']['found']}/{s['answer_key']['of']}" if india else "-"
        L.append(f"| {r['model']} | {s['requests_valid']}/{s['requests_planned']} | {s['findings_written']} | {s['text_fields_verified']}/{s['text_fields']} | "
                 f"{s['ask_answers_complete']}/{len(ASK_QUESTIONS)} | {ak} | {s['seconds']} | {s['cost_usd']} |")
    for r in out:
        s = r["score"]
        L += ["", f"## {r['model']}", ""]
        if s["call_errors"]:
            L.append("**Call errors:** " + "; ".join(map(str, s["call_errors"])))
        u = r["plan"].get("understanding") if isinstance(r["plan"], dict) else None
        if u:
            L += [f"**Understanding:** {u}", ""]
        w = r["written"] if isinstance(r["written"], dict) else {}
        if w.get("headline"):
            L += [f"**Headline:** {w['headline']}", ""]
        for f in (w.get("findings") or [])[:10]:
            if isinstance(f, dict):
                L.append(f"- **{f.get('title')}** ({f.get('importance')})")
                for p in f.get("points") or []:
                    L.append(f"  - {p}")
        for x in w.get("data_warnings") or []:
            L.append(f"- Data warning: {x}")
        L += ["", "Requests that failed:"] + [f"- {x['id']}: {x['error']}" for x in r["runs"] if not x["ok"]][:10]
        if s["rejected_examples"]:
            L += ["", "Wording rejected by the checker:"] + [f"- {x}" for x in s["rejected_examples"]]
        if india:
            k = s["answer_key"]
            L += ["", "Answer key (did the plan look for it?):"] + [f"- {'YES' if v else 'no '} {INDIA_KEY[n]}" for n, v in k["looked_for"].items()]
        for a in r["ask"]:
            ans = a["answer"] if isinstance(a["answer"], dict) else {}
            L += ["", f"**Ask: {a['question']}**", f"- Short answer: {ans.get('short_answer')}"]
            L += [f"  - {p}" for p in ans.get("key_points") or []]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--models", nargs="+", default=[os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")])
    ap.add_argument("--fake", action="store_true", help="no AI: check that the bench itself works")
    ap.add_argument("--out", default="alpha_bench")
    a = ap.parse_args()
    print("Reading the file with the engine (no AI)...")
    rep, frames = load(a.file)
    name, F = next(iter(frames.items()))
    if len(frames) > 1:
        print(f"Several tables found; the bench uses the first one: {name}")
    prof = profile(rep, frames)
    india = "india_retail" in Path(a.file).name.lower()
    by_header = {v: k for k, v in F.canon.items()}
    cols = {"discount": by_header.get("Discount offered", "discount_pct")}
    out_dir = Path(a.out) / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile_sent_to_models.json").write_text(json.dumps(prof, indent=1, default=str), encoding="utf-8")
    results = []
    for mdl in (["fake"] if a.fake else a.models):
        print(f"\n== {mdl} ==")
        client = FakeClient(cols) if a.fake else Client(mdl)
        r = bench_model(client, prof, F.df, india, cols)
        results.append(r)
        safe = re.sub(r"[^\w.-]+", "_", mdl)
        (out_dir / f"{safe}.json").write_text(json.dumps(r, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
        s = r["score"]
        print(f"  valid requests {s['requests_valid']}/{s['requests_planned']}, findings {s['findings_written']}, "
              f"numbers verified {s['text_fields_verified']}/{s['text_fields']}, {s['seconds']}s, ${s['cost_usd']}")
        if india:
            print(f"  answer key: {s['answer_key']['found']}/{s['answer_key']['of']}")
    md = summary_md(Path(a.file).name, results, india)
    (out_dir / "summary.md").write_text(md, encoding="utf-8")
    print(f"\nDone. Send me the folder: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

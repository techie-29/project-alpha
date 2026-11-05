"""The metric + AI brain.

  1. FACT SHEET  - code describes the upload (meanings, metrics it can / cannot calculate, data problems). No raw rows.
  2. PLAN        - the AI fills in 12-20 order forms: what to calculate, split how, on which rows.
  3. CALCULATE   - code checks each form and calculates it exactly (requests.py).
  4. DIG DEEPER  - the AI sees the results and the strongest patterns the engine's own scan found (as numbers) and asks
                   up to 10 follow-up questions. Code calculates those too.
  5. WRITE       - the AI writes finding cards from the exact results, each naming the results it rests on.
  6. CHECK       - code drops every card whose numbers do not come from its cited results, or that is vague (cards.py).
  7. RECORD      - the AI's plan and words are saved; the same upload gives the same report (replay), and costs nothing.
If the AI is off or fails, the engine's own findings are shown instead, through the same gates."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from ..llm import Provider, ProviderError
from ..brief import fact_sheet, numbers_of
from ..cards import gate_all
from . import requests as rq

PROMPT_VERSION = "hybrid-2"

ANALYST = ("You are a senior business analyst. A small or medium business uploaded its own data and wants to know what it most "
           "needs to know. You work with a calculator: you never calculate yourself; you fill in order forms and the tool "
           "calculates them exactly on every row. ")

USEFUL = ("Useful means: money that is made or lost, and where; what changed over time and which groups drive the change; groups "
          "that are far better or worse than the rest; risks (dependence on a few customers, suppliers or products; stock "
          "tied up; customers going quiet); rows or figures that look wrong in the data and change the totals; and ratios over "
          "time (margin, discount rate, return rate), not only totals. Not useful: facts true of every business (a few "
          "customers buy most), splits that only restate a price list (expensive products bring bigger sales), and totals "
          "with nothing to compare them to. ")

PLAN_SYSTEM = (ANALYST + "Read the fact sheet and plan the analysis an expert would run on THIS data. " + USEFUL +
               "Use the named metrics where they fit (measure.metric) and your own combinations where they do not. Cover every "
               "part of the business the data supports, not only sales: each file in the fact sheet that holds its own numbers (returns, "
               "support tickets, reviews, stock, purchases, marketing, footfall, expenses, invoices...) gets at least one request, using "
               "\"file\" to point at it. Use the data problems: check how much they move the totals. "
               "Reply only with JSON: {\"understanding\": \"2-3 sentences: what this business is and what the data can and cannot show\", "
               "\"requests\": [15 to 30 requests, most important first]}.\n" + rq.GRAMMAR)

DIG_SYSTEM = (ANALYST + "You planned an analysis and got the exact results below, plus the strongest patterns the tool's own scan found "
              "(as numbers). Dig deeper where a result is surprising, large in money, or unexplained: which groups drive a change, "
              "whether a pattern holds in each period, how much a data problem moves a figure, what is behind an extreme value. "
              "Drop leads that are small or obvious. Reply only with JSON: {\"requests\": [up to 12 follow-up requests]}. "
              "Use new ids (f1, f2 ...).\n" + rq.GRAMMAR)

WRITE_SYSTEM = (ANALYST + "Write the findings the owner should read, from the exact results below. " + USEFUL +
                "Rules: use only numbers that appear in the results a finding cites (you may round them, write a share as a percent, "
                "or give the change or difference between two of them); every finding compares something (groups, periods, or a part "
                "against the whole) and says how much money is involved; never say one thing caused another (say 'lines up with', "
                "'goes with'); say what the data cannot tell where it matters; skip weak or obvious results; cover the different areas the "
                "results reach (sales, profit, customers, products, stock, buying, marketing, service, costs), not only one; write money "
                "with the currency given in the results or headline numbers and never add a currency symbol that is not given. Reply only with JSON: "
                "{\"headline\": \"one sentence on the state of the business, with numbers\", \"cards\": [8 to 15 of {"
                "\"headline\": \"specific, with the key number\", \"points\": [\"2-3 short points, each with a number\"], "
                "\"money\": {\"amount\": <number from the results>, \"what\": \"what that amount is\"}, "
                "\"why_it_matters\": \"one sentence\", \"look_into\": \"one concrete thing worth looking into next\", "
                "\"tone\": \"risk|strength|data|neutral\", \"area\": \"sales|profit|customers|products|stock|buying|marketing|service|costs|operations|data\", "
                "\"evidence\": [\"request ids it rests on\"], \"chart\": {\"type\": \"bar|line|table|none\", \"evidence\": \"one request id\"}, "
                "\"importance\": \"high|medium|low\", \"strength\": \"Calculated\"}], \"cannot_tell\": [\"what the data cannot show\"]}.")

ASK_PLAN_SYSTEM = (ANALYST + "The owner asks a question about their own data. Plan 1 to 8 requests that answer it, each pointed at the "
                   "file that holds the answer (\"file\"). A broad question (the whole business, all files) gets one request per main file. "
                   "When the data has problems that change the answer (see data_problems), add a request that shows the answer without them. Reply only with JSON: "
                   "{\"requests\": [ ... ]}.\n" + rq.GRAMMAR)

ASK_ANSWER_SYSTEM = ("Answer the owner's question from the exact results below, in plain language. Use only numbers that appear in the "
                     "results (rounded, as a percent, or the change between two of them). Never say one thing caused another. If one of the "
                     "data_problems touches the answer, say so in cannot_tell (in words, without numbers). Reply only "
                     "with JSON: {\"short_answer\": \"1-2 sentences\", \"key_points\": [\"3-6 points, each with a number\"], "
                     "\"how_worked_out\": [\"one line per request used, in words\"], \"what_it_means\": \"1-2 sentences\", "
                     "\"cannot_tell\": \"what the data cannot show\", \"evidence\": [\"request ids used\"]}.")


def _main(frames: dict, report: dict) -> str | None:
    src = (report.get("overview") or {}).get("sources") or {}
    return src.get("sales") or src.get("lines") or next(iter(frames), None)


def _candidates(report: dict, k: int = 20) -> list[dict]:
    """The engine's own strongest patterns, as numbers only (no wording), so the AI is not anchored to template sentences."""
    out = []
    for i in (report.get("insights") or {}).get("items", [])[:60]:
        if i.get("muted"):
            continue
        out.append({"type": i.get("type"), "metric": i.get("metric"), "about": i.get("look_at"), "numbers": i.get("numbers"),
                    "money": i.get("impact"), "strength": i.get("claim"), "when": i.get("when")})
        if len(out) >= k:
            break
    return out


def _key(fs: dict, model: str) -> str:
    h = hashlib.sha256(json.dumps({"fs": fs, "model": model, "v": PROMPT_VERSION}, sort_keys=True, default=str).encode()).hexdigest()
    return h[:24]


class Recorder:
    """Saves what the AI said, keyed by the fact sheet + model + prompt version, and plays it back for the same upload."""

    def __init__(self, data_dir: str | None, key: str):
        self.path = Path(data_dir) / "ai_records" / f"{key}.json" if data_dir else None
        self.saved = {}
        self.replay = False
        if self.path and self.path.exists() and os.environ.get("AI_REPLAY", "1") not in ("0", "false", "no"):
            try:
                self.saved = json.loads(self.path.read_text(encoding="utf-8")); self.replay = True
            except Exception:
                self.saved = {}
        self.new = {}

    def ask(self, provider: Provider, step: str, system: str, payload: dict) -> dict:
        if step in self.saved:
            return self.saved[step]
        ans = provider.complete_json(system, payload, step)
        self.new[step] = ans
        return ans

    def save(self) -> None:
        if self.path and self.new:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({**self.saved, **self.new}, default=str), encoding="utf-8")


def _chart(card: dict, results: dict) -> dict | None:
    rid = (card.get("chart") or {}).get("evidence") or next((e for e in card["evidence"] if (results.get(e) or {}).get("ok")), None)
    r = results.get(rid) if rid else None
    if not r or not r.get("ok"):
        return None
    res = r["result"]
    if not res.get("rows"):
        return None
    kind = (card.get("chart") or {}).get("type")
    by = res.get("by") or []
    if kind in (None, "none"):
        kind = "line" if by and by[0] in ("year", "quarter", "month", "week") else "bar"
    vals = [x["value"] for x in res["rows"] if x["value"] is not None]
    meas = (r["request"] or {}).get("measure") or {}
    pct = meas.get("op") in ("ratio", "share", "share_negative") and vals and max(abs(v) for v in vals) <= 1.5
    if meas.get("metric"):
        from ..metrics.catalogue import BY_ID
        M = BY_ID.get(meas["metric"])
        pct = bool(M and M.fmt == "pct")
    return {"type": kind, "title": (r["request"] or {}).get("question") or "", "by": by, "fmt": "pct" if pct else "number",
            "rows": res["rows"], "request": rid}


def _attach(cards: list, results: dict) -> None:
    for c in cards:
        c["chart_data"] = _chart(c, results)
        c["how"] = [{"id": e, "question": (results[e]["request"] or {}).get("question"), "formula": results[e]["result"].get("formula"),
                     "rows_used": results[e]["rows_used"], "file": results[e].get("file"), "evidence": results[e]["result"].get("evidence")}
                    for e in c["evidence"] if (results.get(e) or {}).get("ok")]


def baseline_cards(report: dict, limit: int = 10) -> tuple[list, list]:
    """The engine's own findings in the card format, through the same gates (used when the AI is off, or to top up)."""
    results, raw = {}, []
    for k, i in enumerate((report.get("insights") or {}).get("items", [])):
        if i.get("muted"):
            continue
        rid = f"b{k}"
        ch = i.get("chart") or {}
        res = {"numbers": i.get("numbers"), "rows": ch.get("rows") or ([{"group": x, "value": v} for x, v in zip(ch.get("x", []), ch.get("values", []))] if ch.get("x") else None),
               "impact": i.get("impact"), "detail_numbers": numbers_of(i.get("numbers"))}
        ev = i.get("evidence") or {}
        results[rid] = {"ok": True, "request": {"question": i.get("title")}, "result": res, "rows_used": int(ev.get("total") or (i.get("numbers") or {}).get("rows") or 1)}
        tone = "data" if i.get("type") in ("data_problem", "extreme_values", "duplicates") else {"bad": "risk", "good": "strength"}.get(i.get("polarity"), "neutral")
        raw.append({"headline": i.get("title"), "points": [i.get("detail")] if i.get("detail") else [], "money": {"amount": i.get("impact"), "what": "involved"},
                    "tone": tone, "area": i.get("area"), "evidence": [rid], "importance": "high" if (i.get("score") or 0) >= 0.5 else "medium",
                    "strength": i.get("claim") if i.get("claim") in ("Calculated", "Supported by evidence") else "Possible", "_item": i.get("id")})
    kept, dropped = gate_all(raw, results, "engine", None, need_rows=True, limit=limit)
    for c in kept:
        c["how"] = [{"id": e, "question": results[e]["request"]["question"], "formula": None, "rows_used": results[e]["rows_used"]} for e in c["evidence"]]
        src = next((i for i in report["insights"]["items"] if i.get("title") == c["headline"]), None)
        if src:
            c["insight_id"] = src["id"]
            ch = src.get("chart") or {}
            if ch.get("rows") or ch.get("values"):
                c["chart_data"] = {"type": ch.get("type", "bar"), "title": ch.get("title", ""), "fmt": ch.get("fmt", "number"),
                                   "rows": ch.get("rows") or [{"group": x, "value": v} for x, v in zip(ch.get("x", []), ch.get("values", []))]}
            c["rows_sample"] = src.get("evidence")
    return kept, dropped


def analyse(report: dict, frames: dict, tables: dict, model: dict, provider: Provider, data_dir: str | None = None) -> dict:
    fs = fact_sheet(report, frames, model, tables)
    report["ai"]["fact_sheet"] = fs
    main = _main(frames, report)
    heads = [t["value"] for t in (report.get("overview") or {}).get("tiles", [])]
    out = {"brain": "metric + AI", "cards": [], "dropped": [], "steps": [], "replayed": False}
    if provider is None or provider.name == "none":
        out["cards"], out["dropped"] = baseline_cards(report)
        out["note"] = "The AI is off, so these are the engine's own findings (after the same quality checks)."
        return out
    rec = Recorder(data_dir, _key(fs, getattr(provider, "model", provider.name)))
    out["replayed"] = rec.replay
    results: dict = {}
    try:
        plan = rec.ask(provider, "plan", PLAN_SYSTEM, {"fact_sheet": fs})
        reqs = plan.get("requests") if isinstance(plan, dict) else None
        out["understanding"] = plan.get("understanding") if isinstance(plan, dict) else None
        rq.run_all(frames, main, reqs or [], results)
        out["steps"].append({"step": "plan", "asked": len(reqs or []), "ok": sum(1 for r in results.values() if r["ok"])})
        dig = rec.ask(provider, "dig", DIG_SYSTEM, {"fact_sheet": {"files": [{k: f[k] for k in ("file", "kind", "groups_to_split_by", "time", "metrics")} for f in fs["files"]]},
                                                    "results": rq.compact(results), "engine_patterns": _candidates(report)})
        n0 = len(results)
        rq.run_all(frames, main, (dig.get("requests") if isinstance(dig, dict) else None) or [], results)
        out["steps"].append({"step": "dig deeper", "asked": len(results) - n0, "ok": sum(1 for r in list(results.values())[n0:] if r["ok"])})
        written = rec.ask(provider, "write", WRITE_SYSTEM, {"results": [r for r in rq.compact(results) if "error" not in r], "headline_numbers": fs["headline_numbers"],
                                                            "data_problems": fs["data_problems"]})
        raw = written.get("cards") if isinstance(written, dict) else None
        kept, dropped = gate_all(raw or [], results, "ai", heads, need_rows=True)
        _attach(kept, results)
        out.update(cards=kept, dropped=dropped, cannot_tell=(written or {}).get("cannot_tell") if isinstance(written, dict) else None)
        hl = (written or {}).get("headline") if isinstance(written, dict) else None
        if hl:
            from ..investigate.verifier import verify_strict
            ok, _ = verify_strict(hl, [r["result"] for r in results.values() if r["ok"]], heads)
            out["headline"] = hl if ok else None
        rec.save()
    except ProviderError as e:
        out["error"] = str(e)[:300]
        rec.save()
    out["requests"] = {rid: {k: v for k, v in r.items() if k != "result"} | ({"formula": r["result"].get("formula"), "rows_used": r["rows_used"]} if r["ok"] else {})
                       for rid, r in results.items()}
    if len(out["cards"]) < 8:                                    # top up with the engine's own findings that pass the same checks
        base, _ = baseline_cards(report, limit=14 - len(out["cards"]))
        have = {c["headline"].lower() for c in out["cards"]}
        out["cards"] += [c for c in base if c["headline"].lower() not in have][: 12 - len(out["cards"])]
    return out


def make_investigator(provider: Provider | None, data_dir: str | None = None):
    def run(report: dict, frames: dict, tables: dict | None = None, model: dict | None = None) -> dict:
        try:
            report["findings"] = analyse(report, frames, tables or {}, model or {"files": {}}, provider or _null(), data_dir)
        except Exception as e:                                 # the report must survive any failure here
            report["findings"] = {"brain": "metric + AI", "cards": baseline_cards(report)[0], "error": f"{type(e).__name__}: {str(e)[:200]}"}
        return report
    return run


def _null():
    from ..llm import NullProvider
    return NullProvider()


# ------------------------------------------------------------------------------------------------ Ask Alpha
def ask(provider: Provider, frames: dict, report: dict, question: str, history: list | None = None) -> dict:
    from ..investigate.verifier import verify_strict
    fs = (report.get("ai") or {}).get("fact_sheet")
    if not fs:
        return {"note": "Re-run the analysis once so Alpha has the file description it needs."}
    main = _main(frames, report)
    plan = provider.complete_json(ASK_PLAN_SYSTEM, {"question": question, "fact_sheet": fs, "earlier_questions": [h.get("question") for h in (history or [])][-5:]}, "ask-plan")
    results = rq.run_all(frames, main, (plan.get("requests") if isinstance(plan, dict) else None) or [])
    good = {k: v for k, v in results.items() if v["ok"]}
    if not good:
        return {"short_answer": None, "note": "Alpha could not turn this question into a calculation on your data. Try naming the measure and the split "
                "(for example: 'profit by region last year').", "calculations": _calcs(results)}
    ans = provider.complete_json(ASK_ANSWER_SYSTEM, {"question": question, "results": [r for r in rq.compact(results) if "error" not in r],
                                                     "data_problems": [{"file": x["file"], "check": x["check"]} for x in (fs.get("data_problems") or [])][:12]}, "ask-answer")
    if not isinstance(ans, dict):
        ans = {}
    nums = [r["result"] for r in good.values()]
    heads = [t["value"] for t in (report.get("overview") or {}).get("tiles", [])]
    out, removed = {}, []
    for f in ("short_answer", "what_it_means", "cannot_tell"):
        t = ans.get(f)
        if isinstance(t, str) and t.strip():
            ok, why = verify_strict(t, nums, heads)
            out[f] = t if ok else None
            if not ok:
                removed.append(f"{f}: {why}")
    for f in ("key_points", "how_worked_out"):
        keep = []
        for t in ans.get(f) or []:
            if isinstance(t, str) and t.strip():
                ok, why = verify_strict(t, nums, heads)
                (keep.append(t) if ok else removed.append(f"{t[:40]}: {why}"))
        out[f] = keep
    if not out.get("short_answer"):
        out["note"] = "Alpha's wording did not match its own calculations, so only the checked points and the calculations are shown."
    out["calculations"] = _calcs(results)
    out["removed"] = removed
    return out


def _calcs(results: dict) -> list[dict]:
    return [{"id": rid, "question": (r["request"] or {}).get("question") if isinstance(r["request"], dict) else None, "ok": r["ok"],
             "formula": r["result"].get("formula") if r["ok"] else None, "rows_used": r.get("rows_used"),
             "result": {k: v for k, v in r["result"].items() if k not in ("evidence",)} if r["ok"] else None,
             "evidence": r["result"].get("evidence") if r["ok"] else None, "error": r.get("error")} for rid, r in results.items()]

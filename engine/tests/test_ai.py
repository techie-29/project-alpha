"""The AI layer, driven by scripted replies (no real AI needed). Checks that code gates every AI suggestion."""
import numpy as np
import pandas as pd
import pytest
from alpha_engine.llm import ScriptedProvider, ProviderError
from alpha_engine.understand.prepare import prepare
from alpha_engine.model.build import build_model
from alpha_engine.investigate.ai import review_concepts, investigate, explain, describe_frames, sanitise, vocabulary
from alpha_engine.investigate.ask import ask
from bench_business import make


class Echo(ScriptedProvider):
    """Calls the given function with the payload each time."""
    def __init__(self, fn):
        super().__init__([]); self.fn = fn
    def complete_json(self, system, payload):
        self.calls.append(payload)
        return self.fn(payload)


def tiny_table(extra):
    r = np.random.default_rng(0)
    df = pd.DataFrame({"_row": range(2, 302), "date": pd.date_range("2024-01-01", periods=300), "zz9": r.integers(0, 400, 300), **extra})
    return {"t.csv": prepare(df, "t.csv")}


def test_ai_review_is_accepted_only_when_the_values_fit():
    tables = tiny_table({})
    model = build_model(tables, [])
    v = model["files"]["t.csv"]["columns"]["zz9"]
    v["needs_confirmation"] = True
    bad = ScriptedProvider([{"columns": [{"file": "t.csv", "column": "zz9", "concept": "rating", "reason": "looks like stars"}]}])
    review_concepts(model, tables, bad)
    assert model["files"]["t.csv"]["columns"]["zz9"]["concept"] != "rating"          # 0..400 cannot be a rating
    good = ScriptedProvider([{"columns": [{"file": "t.csv", "column": "zz9", "concept": "stock_level", "reason": "units on hand"}]}])
    model["files"]["t.csv"]["columns"]["zz9"]["needs_confirmation"] = True
    st = review_concepts(model, tables, good)
    assert model["files"]["t.csv"]["columns"]["zz9"]["concept"] == "stock_level" and model["files"]["t.csv"]["columns"]["zz9"]["source"] == "ai" and st["accepted"] == 1
    assert review_concepts(model, tables, ScriptedProvider([]))["status"] in ("unavailable", "nothing to review")


@pytest.fixture(scope="module")
def analysed(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ai")
    files, truth = make(days=200, n_customers=500, n_products=30)
    files["orders.csv"]["customer_name"] = ["Secret Person " + c for c in files["orders.csv"].customer_id]
    specs = []
    for n, df in files.items():
        df.to_csv(tmp / n, index=False); specs.append({"name": n, "path": str(tmp / n)})
    from alpha_engine import pipeline
    rep = pipeline.analyze("ai1", specs, {}, str(tmp / "data"))
    frames = pipeline.load_state(tmp / "data" / "analyses" / "ai1" / "state.pkl.gz")
    return rep, frames, tmp


def test_ai_sees_no_personal_data(analysed):
    rep, frames, tmp = analysed
    desc = str(describe_frames(frames))
    assert "Secret Person" not in desc and "customer_name" not in desc
    allowed = vocabulary(frames)
    assert sanitise({"Secret Person C00001": 5, "Online": 2}, allowed) == {"[hidden 1]": 5, "Online": 2}


def test_investigation_adds_verified_questions_and_rejects_invented_numbers(analysed):
    rep, frames, tmp = analysed
    script = [
        {"action": "run", "question": "Which channel brings the biggest orders?", "why": "average order by channel", "table": "orders.csv",
         "code": "result = df[df['_ok']].groupby('channel')['revenue'].mean().round(1).to_dict()"},
        lambda p: {"action": "conclude", "question": "Which channel brings the biggest orders?", "area": "sales", "importance": "medium",
                   "answer": f"Online orders average {p['work'][-1]['result']['Online']} per order, which lines up with its growing share."},
        {"action": "run", "question": "Bad code", "why": "x", "code": "import os\nresult = 1"},
        {"action": "conclude", "question": "Something invented", "answer": "Sales grew 87.3% because of the new logo."},
        {"action": "done"}]
    prov = ScriptedProvider(script)
    report = {**rep, "ai": dict(rep["ai"])}
    new = investigate(report, frames, prov)
    assert len(new) == 1 and new[0]["type"] == "ai_question" and "Online" in new[0]["detail"] and new[0]["calculations"]
    sent = str([c["payload"] for c in prov.calls])
    assert "Secret Person" not in sent
    assert investigate({**rep, "ai": {}}, frames, ScriptedProvider([])) == []                 # AI outage: nothing breaks


def test_explanations_must_use_the_findings_numbers(analysed):
    rep, frames, tmp = analysed
    report = {**rep, "insights": {**rep["insights"], "items": [dict(i) for i in rep["insights"]["items"]]}, "briefing": dict(rep["briefing"])}
    first, second = report["insights"]["items"][0], report["insights"]["items"][1]
    prov = ScriptedProvider([{"notes": [{"id": first["id"], "note": "Worth checking soon; this lines up with how the business is changing."},
                                        {"id": second["id"], "note": "This cost the business 999,999 last week."}], "summary": "Steady business overall."}])
    explain(report, prov)
    assert report["insights"]["items"][0].get("ai_note") and not report["insights"]["items"][1].get("ai_note")
    assert report["briefing"]["ai_summary"] == "Steady business overall."


def test_ask_alpha_across_files(analysed):
    rep, frames, tmp = analysed
    def answer(p):
        if not p["work"]:
            return {"action": "run", "why": "count products in stock file", "table": "stock.csv", "code": "result = int(tables['stock.csv']['product_id'].nunique())"}
        n = p["work"][-1]["result"]
        return {"action": "answer", "answer": f"Your stock file tracks {n} products.", "reasoning": f"Counted distinct product ids in the stock file: {n}."}
    r = ask(Echo(answer), str(tmp / "data"), "ai1", "How many products do I track?", rep)
    assert r["verified"] and "30" in r["answer"] and r["calculations"][0]["ok"]
    calls = {"n": 0}
    def liar(p):
        calls["n"] += 1
        return {"action": "answer", "answer": "You track 4,321 products because of good marketing."}
    r2 = ask(Echo(liar), str(tmp / "data"), "ai1", "How many products?", rep)
    assert r2["answer"] is None and calls["n"] >= 2                       # rejected, retried, never shown
    assert ask(Echo(answer), str(tmp / "data"), "missing", "q", rep)["answer"] is None


def test_provider_stops_after_a_fatal_error_and_respects_limits(monkeypatch):
    import io, json as _j, urllib.error, urllib.request
    from alpha_engine.llm import OpenRouterProvider, ProviderFatal, BudgetExceeded, ScriptedProvider, Meter
    calls = []

    def fake_open(req, timeout=0):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 402, "Payment Required", {}, io.BytesIO(_j.dumps({"error": {"message": "This request requires more credits. You requested up to 4096 tokens, but can only afford 900."}}).encode()))
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    p = OpenRouterProvider(api_key="placeholder", model="x/y")
    p.min_interval = 0
    try:
        p.complete_json("s", {}, "plan"); assert False
    except ProviderFatal as e:
        assert "credit" in str(e)
    n = len(calls)
    try:
        p.complete_json("s", {}, "again"); assert False
    except ProviderFatal:
        pass
    assert len(calls) == n == 1                       # no retry on 402, and no second call once switched off
    s = ScriptedProvider([{"a": 1}] * 5); s.meter = Meter(max_calls=2)
    s.complete_json("x", {}); s.complete_json("x", {})
    try:
        s.complete_json("x", {}); assert False
    except BudgetExceeded:
        pass
    assert s.meter.summary()["calls"] == 2


def test_openrouter_cut_off_answer_is_retried_with_more_room(monkeypatch):
    """An empty answer that used up all its tokens (the model was still thinking) is retried with more room and low thinking."""
    import io, json as _j, urllib.request
    from alpha_engine.llm import OpenRouterProvider
    sent = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=0):
        body = _j.loads(req.data)
        sent.append((body["max_tokens"], body.get("reasoning")))
        if len(sent) == 1:
            out = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}], "usage": {"prompt_tokens": 10, "completion_tokens": body["max_tokens"], "cost": 0.001}}
        else:
            out = {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.001}}
        return Resp(_j.dumps(out).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    p = OpenRouterProvider(api_key="k", model="m"); p.min_interval = 0
    assert p.complete_json("s", {"a": 1}, "write") == {"ok": True}
    assert sent[1][0] == 2 * sent[0][0] and sent[1][1] == {"effort": "low"}

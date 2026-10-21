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

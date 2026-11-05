"""Metric + AI brain, end to end with a scripted stand-in for the AI: plan -> calculate -> dig deeper -> write -> gates,
replay of a saved run, the no-AI fallback, and Ask Alpha's structured answer."""
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_engine import pipeline
from alpha_engine.llm import ScriptedProvider, ProviderError, Provider


class ByStep(Provider):
    """Answers by step name (plan / dig / write); anything else (column review while reading) gets an empty answer."""
    name = "bystep"

    def __init__(self, answers):
        super().__init__(); self.answers = answers; self.model = "test/model"; self.steps = []

    def complete_json(self, system, payload, purpose=""):
        self.meter.add(purpose, 0, 0, 0, 0)
        self.steps.append(purpose)
        a = self.answers.get(purpose, {})
        return a(payload) if callable(a) else a
from alpha_engine.hybrid import make_investigator, ask
from alpha_engine.hybrid import requests as rq

R = np.random.default_rng(11)


def _shop(n=4000):
    d = pd.date_range("2022-01-01", "2024-12-31", periods=n)
    yr = d.year.to_numpy()
    q = R.integers(1, 6, n); pr = R.choice([80.0, 150.0, 400.0], n)
    disc = R.choice([0.0, 0.0, 0.0, 0.08, 0.15], n)
    sales = np.round(q * pr * (1 - disc), 2)
    base_m = np.where(yr == 2022, 0.22, np.where(yr == 2023, 0.15, 0.07))        # planted: margin falls each year
    m = base_m - np.where(disc > 0.1, 0.12, 0) + R.normal(0, 0.04, n)              # planted: big discounts cut margin
    df = pd.DataFrame({"Invoice No": [f"INV{i:05d}" for i in range(n)], "Invoice Date": d.strftime("%d-%m-%Y"), "Customer": [f"C{x:03d}" for x in R.integers(1, 250, n)],
                       "Branch": R.choice(["Andheri", "Thane", "Pune"], n), "Category": R.choice(["Grocery", "Dairy", "Snacks", "Home"], n),
                       "Qty": q, "Rate": pr, "Disc %": disc, "Net Amount": sales, "Profit": np.round(sales * m, 2)})
    return df


def _files(df, name="shop.csv"):
    d = tempfile.mkdtemp()
    p = Path(d) / name
    df.to_csv(p, index=False)
    return d, [{"name": name, "path": str(p)}]


PLAN = {"understanding": "A retailer with three branches.", "requests": [
    {"id": "q1", "question": "Margin by year", "measure": {"metric": "margin"}, "by": [{"time": "year"}]},
    {"id": "q2", "question": "Share of lines losing money", "measure": {"metric": "loss_line_share"}},
    {"id": "q3", "question": "Margin by discount band", "measure": {"op": "ratio", "col": "profit", "den": "revenue"}, "by": [{"col": "discount_pct", "bins": [0, 0.1, 1]}]},
    {"id": "q4", "question": "Money lost on loss lines", "measure": {"metric": "loss_amount"}},
    {"id": "q5", "question": "broken", "measure": {"op": "explode"}},
    {"id": "q6", "question": "Sales by branch", "measure": {"op": "sum", "col": "revenue"}, "by": ["Branch"]}]}
DIG = {"requests": [{"id": "f1", "question": "Margin by year and branch", "measure": {"metric": "margin"}, "by": [{"time": "year"}, "Branch"]},
                    {"id": "f2", "question": "Lines losing money in 2024", "measure": {"op": "share"}, "filter": [{"col": "profit", "op": "<", "value": 0}, {"col": "date", "op": ">=", "value": "2024-01-01"}]}]}


def _write(payload):
    res = {r["id"]: r["result"] for r in payload["results"]}
    y = {x["group"]: x["value"] for x in res["q1"]["rows"]}
    band = {x["group"]: x["value"] for x in res["q3"]["rows"]}
    lo, hi = sorted(band.values(), reverse=True)[:2]
    loss = res["q4"]["overall"]
    return {"headline": f"Margin fell from {y['2022'] * 100:.1f}% in 2022 to {y['2024'] * 100:.1f}% in 2024.", "cards": [
        {"headline": f"Margin fell from {y['2022'] * 100:.1f}% in 2022 to {y['2024'] * 100:.1f}% in 2024", "points": [f"It was {y['2023'] * 100:.1f}% in 2023."],
         "money": {"amount": -loss, "what": "lost on loss-making lines"}, "tone": "risk", "area": "profit", "evidence": ["q1", "q4"], "chart": {"type": "line", "evidence": "q1"}, "importance": "high"},
        {"headline": f"Big discounts go with a margin of {hi * 100:.1f}% vs {lo * 100:.1f}%", "points": [f"Lines with over 10% off earn {hi * 100:.1f}%."],
         "money": {"amount": -loss, "what": "lost on loss-making lines"}, "tone": "risk", "area": "profit", "evidence": ["q3", "q4"], "importance": "high"},
        {"headline": "Margins could be better", "points": ["Some lines are weak."], "evidence": ["q1"], "importance": "high"},          # vague: must be dropped
        {"headline": f"Margin fell to 3.3% in 2024 because of discounts", "money": {"amount": -loss}, "evidence": ["q1", "q4"]},  # made up and causal
    ]}


def test_plan_calculate_dig_write_and_gates():
    d, files = _files(_shop())
    prov = ByStep({"plan": PLAN, "dig": DIG, "write": _write})
    rep = pipeline.analyze("h1", files, {}, d, prov, investigate=make_investigator(prov, d))
    f = rep["findings"]
    heads = [c["headline"] for c in f["cards"] if c["source"] == "ai"]
    assert len(heads) == 2 and heads[0].startswith("Margin fell from")
    assert any("Margins could be better" == x["headline"] for x in f["dropped"])
    assert any("3.3%" in x["headline"] for x in f["dropped"])
    assert f["requests"]["q5"]["ok"] is False                           # a bad form is refused, not run
    assert f["requests"]["f2"]["ok"] and f["steps"][1]["ok"] == 2
    c0 = f["cards"][0]
    assert c0["chart_data"]["type"] == "line" and c0["chart_data"]["fmt"] == "pct" and len(c0["chart_data"]["rows"]) == 3
    assert c0["how"][0]["formula"].startswith("Profit margin") and c0["how"][0]["evidence"]["rows"]
    assert "Row in file" in c0["how"][0]["evidence"]["columns"]
    assert [x for x in prov.steps if x in ("plan", "dig", "write")] == ["plan", "dig", "write"]
    assert "fact_sheet" in rep["ai"]
    # replay: same upload, an AI that would fail -> same cards, no calls
    class Broken(Provider):
        name = "broken"; model = ""
        def complete_json(self, *a, **k):
            raise ProviderError("should not be called")
    prov2 = Broken(); prov2.model = prov.model
    rep2 = pipeline.analyze("h2", files, {}, d, prov2, investigate=make_investigator(prov2, d))
    assert rep2["findings"]["replayed"] and [c["headline"] for c in rep2["findings"]["cards"] if c["source"] == "ai"] == heads


def test_numbers_are_exact():
    df = _shop()
    d, files = _files(df)
    st_dir = tempfile.mkdtemp()
    rep = pipeline.analyze("h3", files, {}, st_dir, None)
    frames = pipeline.load_state(Path(st_dir) / "analyses" / "h3" / "state.pkl.gz")
    F = next(iter(frames.values()))
    out = rq.run(F, PLAN["requests"][0])
    yr = pd.to_datetime(df["Invoice Date"], format="%d-%m-%Y").dt.year
    want = df.groupby(yr)["Profit"].sum() / df.groupby(yr)["Net Amount"].sum()
    for r in out["rows"]:
        assert abs(r["value"] - want[int(r["group"])]) < 1e-6
    share = rq.run(F, {"measure": {"op": "share"}, "filter": [{"col": "profit", "op": "<", "value": 0}]})
    assert abs(share["overall"] - (df["Profit"] < 0).mean()) < 1e-9


def test_without_ai_the_engine_findings_pass_the_same_gates():
    d, files = _files(_shop())
    rep = pipeline.analyze("h4", files, {}, d, None)
    f = rep["findings"]
    assert f["cards"] and all(c["source"] == "engine" for c in f["cards"])
    assert all(any(ch.isdigit() for ch in c["headline"]) for c in f["cards"])


def test_ask_alpha_gives_a_checked_structured_answer():
    d, files = _files(_shop())
    rep = pipeline.analyze("h5", files, {}, d, None)
    rep["ai"]["fact_sheet"] = rep["ai"].get("fact_sheet") or {"files": []}
    from alpha_engine.hybrid.brain import fact_sheet
    tables, links, model = pipeline._understand(files, {}, pipeline.NullProvider(), None)
    frames = pipeline.load_state(Path(d) / "analyses" / "h5" / "state.pkl.gz")
    rep["ai"]["fact_sheet"] = fact_sheet(rep, frames, model, tables)

    def answer(payload):
        r = payload["results"][0]["result"]["rows"]
        a, b = r[0]["value"], r[-1]["value"]
        return {"short_answer": f"Profit margin went from {a * 100:.1f}% to {b * 100:.1f}%.", "key_points": [f"{r[0]['group']}: {a * 100:.1f}%", "It is 99.9% better now."],
                "how_worked_out": ["Profit / sales for each year."], "what_it_means": "Margins are thinner.", "cannot_tell": "Why it changed.", "evidence": ["a1"]}
    prov = ScriptedProvider([{"requests": [{"id": "a1", "question": "margin by year", "measure": {"metric": "margin"}, "by": [{"time": "year"}]}]}, answer])
    out = ask(prov, frames, rep, "How is profit going?")
    assert out["short_answer"].startswith("Profit margin went from")
    assert len(out["key_points"]) == 1 and any("99.9" in x for x in out["removed"])     # the made-up point is removed
    assert out["calculations"][0]["ok"] and out["calculations"][0]["evidence"]["rows"]

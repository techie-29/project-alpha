"""Full-AI brain end to end with a stand-in AI that writes real pandas code."""
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_engine.llm import Provider, ProviderError
from alpha_engine.ai_analyst import analyze, ask
from alpha_engine.ai_analyst.pipeline import load_state

R = np.random.default_rng(5)


class ByStep(Provider):
    name = "bystep"

    def __init__(self, answers):
        super().__init__(); self.answers = answers; self.model = "test/model"; self.steps = []; self.payloads = {}

    def complete_json(self, system, payload, purpose=""):
        self.meter.add(purpose, 0, 0, 0, 0)
        self.steps.append(purpose); self.payloads[purpose] = payload
        a = self.answers.get(purpose, {})
        return a(payload) if callable(a) else a


def _file():
    n = 1500
    d = pd.date_range("2023-01-01", "2024-12-31", periods=n)
    amt = np.round(R.uniform(100, 2000, n), 2)
    prof = np.round(amt * np.where(d.year == 2023, 0.2, 0.08) + R.normal(0, 10, n), 2)
    df = pd.DataFrame({"Bill Date": d.strftime("%d/%m/%Y"), "Customer Name": [f"Person {i % 90}" for i in range(n)], "Outlet": R.choice(["East", "West"], n),
                       "Bill Amount": [f"₹{x:,.2f}" for x in amt], "Profit": prof})
    p = Path(tempfile.mkdtemp()) / "bills.csv"; df.to_csv(p, index=False)
    return p, df, amt, prof


BAD_SETUP = "df['Bill Date'] = pd.to_datetime(df['Bill Date'], format='%Y-%m-%d')"
SETUP = ("df['Bill Date'] = pd.to_datetime(df['Bill Date'], format='%d/%m/%Y')\n"
         "df['amount'] = pd.to_numeric(df['Bill Amount'].str.replace('₹', '').str.replace(',', ''))\n"
         "df['year'] = df['Bill Date'].dt.year\ntables['bills.csv'] = df")


def _understand(payload):
    return {"business": "A shop with two outlets.", "columns": [{"file": "bills.csv", "column": "Bill Amount", "meaning": "sale value"}],
            "setup": BAD_SETUP, "checks": [{"id": "c1", "question": "Rows with profit above the sale", "code": "result = {'rows': int((df['Profit'] > df['amount']).sum())}"},
                                           {"id": "c2", "question": "evil", "code": "import os"}]}


def _write(payload):
    res = {r["id"]: r["result"] for r in payload["results"]}
    m = res["q1"]
    a, b = m["margin"]["2023"], m["margin"]["2024"]
    return {"headline": f"Margin went from {a * 100:.1f}% in 2023 to {b * 100:.1f}% in 2024.",
            "key_figures": [{"label": "Sales", "value": res["q2"]["sales"], "format": "money", "evidence": ["q2"]},
                            {"label": "Invented", "value": 123456.0, "format": "money", "evidence": ["q2"]}],
            "data_quality": [{"headline": f"{res['c1']['rows']} rows show profit above the sale", "tone": "data", "evidence": ["c1"]}],
            "cards": [{"headline": f"Margin fell from {a * 100:.1f}% to {b * 100:.1f}%", "points": [f"Profit was {m['profit']['2024']:,.0f} in 2024."],
                       "money": {"amount": m["profit"]["2024"], "what": "profit in 2024"}, "tone": "risk", "evidence": ["q1"],
                       "chart": {"type": "bar", "evidence": "q1", "y": "margin"}, "importance": "high"},
                      {"headline": "Margin fell to 2.2% in 2024", "evidence": ["q1"]}]}


ANSWERS = {"understand": _understand, "fix_setup": {"setup": SETUP},
           "plan": {"questions": [{"id": "q1", "question": "Margin by year", "code": "g = df.groupby('year')\nresult = {'margin': (g['Profit'].sum() / g['amount'].sum()).to_dict(), 'profit': g['Profit'].sum().to_dict()}"},
                                  {"id": "q2", "question": "Total sales", "code": "result = {'sales': float(df['amount'].sum())}"}]},
           "dig": {"questions": [{"id": "f1", "question": "Margin by outlet", "code": "def m(x):\n    return x['Profit'].sum() / x['amount'].sum()\nresult = {k: m(v) for k, v in df.groupby('Outlet')}"}]},
           "write": _write}


def test_full_ai_end_to_end():
    p, df, amt, prof = _file()
    d = tempfile.mkdtemp()
    prov = ByStep(ANSWERS)
    rep = analyze("a1", [{"name": "bills.csv", "path": str(p)}], d, prov)
    f = rep["findings"]
    assert "Customer Name" in rep["files"][0]["withheld_personal_columns"]
    assert "Person" not in str(prov.payloads)                                     # no personal values ever reached the AI
    assert prov.steps[:3] == ["understand", "fix_setup", "plan"] and f["setup"] == SETUP
    code = {c["id"]: c for c in f["code"]}
    assert code["c2"]["ok"] is False and "not allowed" in code["c2"]["error"]
    assert code["q1"]["ok"] and code["f1"]["ok"]
    assert [c["headline"].split(" ")[0] for c in f["cards"]] == ["Margin"] and len(f["cards"]) == 1
    assert any("2.2%" in x["headline"] for x in f["dropped"]) and any("Invented" in x["headline"] for x in f["dropped"])
    assert [k["label"] for k in f["key_figures"]] == ["Sales"] and abs(f["key_figures"][0]["value"] - amt.sum()) < 0.01
    assert f["data_quality"] and f["cards"][0]["chart_data"]["fmt"] == "pct" and f["cards"][0]["how"][0]["code"]
    yr = pd.to_datetime(df["Bill Date"], format="%d/%m/%Y").dt.year
    true = {y: prof[yr == y].sum() / amt[yr == y].sum() for y in (2023, 2024)}
    assert f"{true[2023] * 100:.1f}%" in f["cards"][0]["headline"]
    # replay with an AI that must not be called
    class Broken(Provider):
        name = "broken"; model = "test/model"
        def complete_json(self, *a, **k):
            raise ProviderError("should not be called")
    rep2 = analyze("a2", [{"name": "bills.csv", "path": str(p)}], d, Broken())
    assert rep2["findings"]["replayed"] and [c["headline"] for c in rep2["findings"]["cards"]] == [c["headline"] for c in f["cards"]]
    # Ask Alpha on the saved state
    st = load_state(Path(d) / "analyses" / "a1")
    prov3 = ByStep({"ask-plan": {"questions": [{"id": "a1", "question": "sales by outlet", "code": "result = df.groupby('Outlet')['amount'].sum()"}]},
                    "ask-answer": lambda pl: {"short_answer": f"East sold {pl['results'][0]['result']['East']:,.2f}.", "key_points": ["West sold 512,000.00."]}})
    out = ask(prov3, st["tables"], st["setup"], st["profile"], "Which outlet sells more?")
    assert out["short_answer"].startswith("East sold") and out["key_points"] == [] and out["calculations"][0]["ok"]


def test_without_ai_it_says_so():
    p, *_ = _file()
    from alpha_engine.llm import NullProvider
    rep = analyze("a3", [{"name": "bills.csv", "path": str(p)}], tempfile.mkdtemp(), NullProvider())
    assert "needs the AI" in rep["findings"]["error"] and rep["findings"]["cards"] == []

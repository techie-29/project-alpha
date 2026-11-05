"""Card gates and the AI fact sheet."""
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from alpha_engine.cards import gate_all
from alpha_engine import pipeline
from alpha_engine.brief import fact_sheet, raw_profile

RES = {"q1": {"ok": True, "rows_used": 2534, "result": {"rows": [{"group": "2010", "value": 0.1402}, {"group": "2013", "value": 0.0621}], "overall": 0.1134}},
       "q2": {"ok": True, "rows_used": 1240, "result": {"overall": -358500.0, "rows_used": 1240}}}


def test_gates_keep_specific_cards_and_drop_vague_ones():
    good = {"headline": "Margin fell from 14.0% in 2010 to 6.2% in 2013", "points": ["Down 7.8 points over three years."], "money": {"amount": -358500.0, "what": "lost on loss-making lines"},
            "evidence": ["q1", "q2"], "tone": "risk", "importance": "high"}
    vague = {"headline": "Profitability could be improved", "points": ["Some products have low margins."], "evidence": ["q1"], "importance": "high"}
    madeup = {"headline": "Margin fell to 4.1% in 2013", "points": [], "money": {"amount": -358500.0}, "evidence": ["q1", "q2"], "importance": "medium"}
    nomoney = {"headline": "Margin was 14.0% in 2010 vs 6.2% in 2013", "evidence": ["q1"]}
    causal = {"headline": "Margin fell to 6.2% in 2013 because of discounts", "money": {"amount": -358500.0}, "evidence": ["q1", "q2"]}
    copy = dict(good, points=["It went from 14.0% to 6.2%."])
    kept, dropped = gate_all([good, vague, madeup, nomoney, causal, copy], RES, "t")
    assert [c["headline"] for c in kept] == [good["headline"]]
    assert len(dropped) == 5


def test_fact_sheet_has_meanings_metrics_and_no_personal_data():
    r = np.random.default_rng(1); n = 600
    df = pd.DataFrame({"Order ID": [f"O{i}" for i in range(n)], "Order Date": pd.date_range("2024-01-01", periods=n, freq="7h").strftime("%Y-%m-%d"),
                       "Customer Name": [f"Person {i % 80}" for i in range(n)], "Email": [f"p{i % 80}@x.com" for i in range(n)],
                       "Region": r.choice(["North", "South"], n), "Quantity": r.integers(1, 5, n), "Sales": np.round(r.uniform(50, 500, n), 2)})
    d = tempfile.mkdtemp(); p = Path(d) / "s.csv"; df.to_csv(p, index=False)
    rep = pipeline.analyze("t", [{"name": "s.csv", "path": str(p)}], {}, d, None)
    st = pipeline.load_state(Path(d) / "analyses" / "t" / "state.pkl.gz")
    tables, links, model = pipeline._understand([{"name": "s.csv", "path": str(p)}], {}, pipeline.NullProvider(), None)
    fs = fact_sheet(rep, st, model, tables)
    f = fs["files"][0]
    names = {c["name"] for c in f["columns"]}
    assert "Customer Name" not in names and "Email" not in names
    assert set(f["withheld_personal_columns"]) >= {"Customer Name", "Email"}
    assert any(m["id"] == "revenue" for m in f["metrics"]["available"])
    assert any(m["id"] == "margin" for m in f["metrics"]["blocked"])           # no profit column: margin is blocked, and it says why
    text = str(fs)
    assert "Person 1" not in text and "@x.com" not in text
    rp = raw_profile(tables)
    assert "Email" in rp[0]["withheld_personal_columns"] and "Person" not in str(rp)

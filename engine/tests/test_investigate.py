import numpy as np
import pandas as pd
import pytest
from alpha_engine.investigate import sandbox
from alpha_engine.investigate.verifier import verify
from alpha_engine.investigate.loop import investigate_one, sanitise, vocabulary
from alpha_engine.investigate.ask import ask
from alpha_engine.llm import ScriptedProvider, ProviderError


def frame():
    r = np.random.default_rng(0)
    return pd.DataFrame({"_t": pd.date_range("2024-01-01", periods=200), "region": ["North", "South"] * 100, "amount": r.normal(100, 5, 200),
                         "customer_name": ["Secret Person"] * 200})


# ---- sandbox ----
def test_sandbox_runs_a_calculation():
    out = sandbox.run("result = df.groupby('region').amount.sum()", frame())
    assert out["ok"] and set(out["result"]) == {"North", "South"}


@pytest.mark.parametrize("code", [
    "import os\nresult = 1", "result = open('/etc/passwd').read()", "result = df.to_csv('/tmp/x.csv')", "result = ().__class__",
    "result = eval('1+1')", "result = pd.read_csv('http://example.com/a.csv')", "def f():\n    return 1\nresult = f()",
    "result = getattr(df, 'amount')", "result = [c for c in ().__class__.__mro__]", "result = df.query('amount > 1')", "result = __import__('os')"])
def test_sandbox_refuses_dangerous_code(code):
    out = sandbox.run(code, frame())
    assert not out["ok"] and "not allowed" in out["error"]


def test_sandbox_limits_time_and_reports_errors():
    assert not sandbox.run("result = df.nope.sum()", frame())["ok"]
    out = sandbox.run("x = 0\nwhile True:\n    x += 1\nresult = x", frame(), timeout=3, cpu_s=2)
    assert not out["ok"]
    assert not sandbox.run("result = [0] * (10**10)", frame(), memory_mb=500)["ok"]


# ---- verifier ----
def test_verifier_accepts_backed_numbers_and_rejects_made_up_ones():
    produced = [{"before": 36603.2, "after": 91427.9, "relative": 1.4978}]
    assert verify("That week was 91.4K against 36.6K, up 150%.", produced)[0]
    ok, why = verify("Sales rose 73% that week.", produced)
    assert not ok and "73" in why
    assert verify("It rose in week 3 of 2021 on 20 Dec 2021.", produced)[0]


def test_verifier_refuses_causal_wording():
    assert not verify("The promotion caused the rise.", [])[0]
    assert not verify("This was due to a price cut.", [])[0]
    assert verify("This lines up with the Social Media channel.", [])[0]


# ---- loop ----
def finding():
    return {"title": "Sales spiked in the week of 20 Dec 2021", "detail": "That week was 91,428 against a typical 36,603.", "when": "20 Dec 2021",
            "slice_col": None, "slice_val": None, "label": "Net sales", "currency": "USD", "level": "confirmed",
            "numbers": {"before": 36603.0, "after": 91428.0, "relative": 1.4978}, "drivers": None}


def table():
    df = frame()
    return {"name": "t", "df": df, "roles": {"region": {"role": "category", "unique": 2}, "customer_name": {"role": "category", "unique": 1}, "amount": {"role": "measure"}}, "money_col": "amount", "currency_col": None, "step": "day"}


def test_loop_runs_code_then_accepts_verified_summary():
    t = table()
    prov = ScriptedProvider([
        {"action": "run", "why": "split by region", "code": "result = df.groupby('region').amount.sum().round(0)"},
        lambda payload: {"action": "finish", "summary": f"Both regions are close; North was {payload['results_so_far'][0]['result']['North']:.0f}. It lines up with no single region.", "checks": ["region split"]}])
    res = investigate_one(prov, finding(), t, vocabulary(t["df"], t["roles"]))
    assert res["verified"] and "North" in res["summary"] and res["steps"] == 1
    # privacy: the model never saw the personal column's values, only the aggregated result
    seen = str(prov.calls)
    assert "Secret Person" not in seen and "customer_name" in seen


def test_loop_rejects_invented_numbers_and_survives_bad_code_and_outage():
    t = table()
    bad = ScriptedProvider([{"action": "finish", "summary": "Sales rose 99% because of a promotion."}])
    assert investigate_one(bad, finding(), t, set())["summary"] is None
    evil = ScriptedProvider([{"action": "run", "why": "x", "code": "import os\nresult = os.listdir('/')"}, {"action": "finish", "summary": "I could not check this."}])
    r = investigate_one(evil, finding(), t, set())
    assert r["summary"] == "I could not check this." and not r["calculations"][0]["ok"]
    assert investigate_one(ScriptedProvider([]), finding(), t, set()) is None


def test_sanitise_hides_unknown_strings():
    allowed = vocabulary(frame(), {"region": {"role": "category", "unique": 2}, "customer_name": {"role": "category", "unique": 1}})
    assert sanitise({"North": 1, "Secret Person": 2, "when": "2024-01-02"}, allowed) == {"North": 1, "[hidden 1]": 2, "[hidden 2]": "2024-01-02"}
    assert "Secret Person" not in allowed


# ---- ask ----
def test_ask_alpha_answers_with_verified_numbers(tmp_path):
    from alpha_engine.pipeline import save_state
    import types, gzip, pickle
    df = frame()
    slim = [{"name": "t", "time_col": "_t", "money_col": "amount", "currency_col": None, "slices": ["region"], "ok": np.ones(len(df), bool),
             "roles": {"region": {"role": "category", "unique": 2}}, "df": df, "step": "day", "notes": []}]
    d = tmp_path / "analyses" / "a9"; d.mkdir(parents=True)
    with gzip.open(d / "state.pkl.gz", "wb") as fh:
        pickle.dump(slim, fh)
    prov = ScriptedProvider([
        {"action": "run", "why": "rows per region", "code": "result = df.region.value_counts()"},
        {"action": "finish", "answer": "North has 100 rows and South has 100 rows."}])
    r = ask(prov, str(tmp_path), "a9", "How many rows per region?")
    assert r["verified"] and "100" in r["answer"] and r["calculations"][0]["ok"]
    prov2 = ScriptedProvider([{"action": "finish", "answer": "There were 777 rows."}])
    r2 = ask(prov2, str(tmp_path), "a9", "How many rows?")
    assert r2["answer"] is None and "safely" in r2["note"]
    assert ask(prov, str(tmp_path), "missing", "q")["answer"] is None

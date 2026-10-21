import numpy as np
import pandas as pd
import pytest
from alpha_engine.investigate import sandbox
from alpha_engine.investigate.verifier import verify


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



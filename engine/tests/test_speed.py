"""Speed changes must never change an answer. All data is made up for the test."""
import json
import os
import tempfile
import threading
import time
from pathlib import Path
import numpy as np
import pandas as pd
import alpha_engine  # noqa: F401  (registers the .alpha helpers)
from alpha_engine import pipeline
from alpha_engine.llm import OpenRouterProvider, Provider
from alpha_engine.understand import reader

R = np.random.default_rng(11)


def test_fast_trim_gives_exactly_the_plain_answer():
    vals = np.array([" a", "b ", "C", None, np.nan, 1, 2.5, pd.Timestamp("2024-01-01"), "", "  "], dtype=object)
    for dt in (object, "string", "str", "category"):
        s = pd.Series(R.choice(vals, 6000), index=R.permutation(6000) * 3)
        s = s if dt is object else s.astype(dt)
        for plain, fast in ((s.astype(str).str.strip(), s.alpha.strip_str()), (s.astype("string").str.strip(), s.alpha.strip_string())):
            assert plain.equals(fast) and plain.dtype == fast.dtype and plain.index.equals(fast.index), dt


def test_fast_excel_reader_reads_the_same_cells():
    tmp = Path(tempfile.mkdtemp()) / "b.xlsx"
    n = 3000
    df = pd.DataFrame({"id": [f"X{i}" for i in range(n)], "when": pd.date_range("2024-01-01", periods=n, freq="h"),
                       "qty": R.integers(1, 9, n), "price": R.uniform(1, 99, n).round(2), "note": R.choice(["ok", "", None, " late "], n)})
    with pd.ExcelWriter(tmp) as w:
        df.to_excel(w, sheet_name="Data", index=False)
        df.head(50).to_excel(w, sheet_name="Small", index=False)
    fast = reader._read_book(str(tmp))
    slow = pd.read_excel(tmp, sheet_name=None, header=None, na_values=reader.NA)
    assert set(fast) == set(slow)
    for k in slow:
        pd.testing.assert_frame_equal(fast[k], slow[k], check_dtype=False)


def _report(tmp: str, threads: str, r) -> dict:
    os.environ["ALPHA_THREADS"] = threads
    try:
        n = 4000
        df = pd.DataFrame({"order_id": [f"O{i:05d}" for i in range(n)], "order_date": pd.date_range("2023-01-01", periods=n, freq="5h").strftime("%Y-%m-%d"),
                           "region": r.choice(["North", "South", "East", "West"], n), "channel": r.choice(["Web", "Shop", "Phone"], n),
                           "status": r.choice(["Delivered"] * 8 + ["Cancelled", "Returned"], n)})
        df["order_total"] = np.round(r.uniform(100, 900, n) * np.where(df["region"] == "North", 1.4, 1.0), 2)
        p = Path(tmp) / f"s{threads}.csv"; df.to_csv(p, index=False)
        rep = pipeline.analyze("sp", [{"id": 1, "name": "s.csv", "path": str(p)}], {}, tmp, None)
        return {"items": [(i["title"], i.get("p"), i.get("q")) for i in rep["insights"]["items"]], "tiles": rep["overview"]["tiles"]}
    finally:
        os.environ.pop("ALPHA_THREADS", None)


def test_shuffle_tests_side_by_side_give_the_same_findings():
    one = _report(tempfile.mkdtemp(), "1", np.random.default_rng(4))
    many = _report(tempfile.mkdtemp(), "4", np.random.default_rng(4))
    assert one["items"] and json.dumps(one, default=str) == json.dumps(many, default=str)


def test_each_ai_step_asks_for_its_own_thinking_effort(monkeypatch):
    monkeypatch.delenv("AI_REASONING", raising=False)
    p = OpenRouterProvider(api_key="test-key")
    body = lambda purpose: json.loads(p._body("s", "{}", 100, purpose=purpose))
    assert body("plan")["reasoning"] == {"effort": "medium"} and body("write")["reasoning"] == {"effort": "medium"}   # plan writes code here
    assert "reasoning" not in body("something-else")
    assert body("read-columns")["reasoning"] == {"effort": "low"}
    assert json.loads(p._body("s", "{}", 100, force_low=True, purpose="write"))["reasoning"] == {"effort": "low"}
    monkeypatch.setenv("AI_REASONING", "high")
    assert json.loads(OpenRouterProvider(api_key="test-key")._body("s", "{}", 100, purpose="plan"))["reasoning"] == {"effort": "high"}
    monkeypatch.setenv("AI_REASONING", "model")
    assert "reasoning" not in json.loads(OpenRouterProvider(api_key="test-key")._body("s", "{}", 100, purpose="plan"))
    assert OpenRouterProvider(api_key="test-key").timeout >= 300


class _Slow(Provider):
    name = "slow"

    def __init__(self):
        super().__init__()
        self.live = self.most = 0
        self.lock = threading.Lock()

    def complete_json(self, system, payload, purpose=""):
        with self.lock:
            self.live += 1; self.most = max(self.most, self.live)
        time.sleep(0.4)
        with self.lock:
            self.live -= 1
        return {"columns": {}}


def test_unclear_columns_of_several_tables_are_asked_at_the_same_time():
    pipeline._CACHE.clear()
    tmp = Path(tempfile.mkdtemp())
    files = []
    for k in range(4):
        df = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=200).strftime("%Y-%m-%d"), "Amount": R.uniform(1, 9, 200).round(2),
                           "Thing": R.integers(1000, 1003, 200)})          # three repeating numbers: a code or an amount? unclear
        p = tmp / f"t{k}.csv"; df.to_csv(p, index=False)
        files.append({"id": k, "name": f"t{k}.csv", "path": str(p)})
    prov = _Slow()
    t = time.time()
    tables = {f["name"]: pipeline._load(f, {}, prov) for f in files}
    pipeline._review_all(tables, prov)
    assert all((tb.ai_status or {}).get("status") == "ok" for tb in tables.values())
    assert prov.most >= 2 and time.time() - t < 4 * 0.4 + 1.0

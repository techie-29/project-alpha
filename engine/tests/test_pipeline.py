import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from bench import business


@pytest.fixture()
def env(tmp_path, monkeypatch):
    up = tmp_path / "uploads"; up.mkdir()
    monkeypatch.setenv("ENGINE_UPLOAD_DIR", str(up)); monkeypatch.setenv("ENGINE_DATA_DIR", str(tmp_path / "data")); monkeypatch.setenv("ENGINE_API_KEY", "k")
    import importlib, alpha_engine.api as api
    importlib.reload(api)
    return api, up, tmp_path


def make_files(up):
    df = business(1, years=3).drop(columns=["_row"])
    df.to_csv(up / "shop.csv", index=False)
    return df


def wait(client, aid, tries=200):
    import time
    for _ in range(tries):
        j = client.get(f"/v1/jobs/{aid}", headers={"x-engine-key": "k"}).json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.5)
    raise AssertionError("timeout")


def test_end_to_end_through_the_api(env):
    api, up, tmp = env
    make_files(up)
    c = TestClient(api.app)
    H = {"x-engine-key": "k"}
    assert c.post("/v1/read", json={"files": [{"name": "shop.csv", "path": str(up / "shop.csv")}], "use_ai": False}).status_code == 401
    r = c.post("/v1/read", headers=H, json={"files": [{"name": "shop.csv", "path": str(up / "shop.csv")}], "use_ai": False}).json()
    cols = {x["name"]: x for x in r["files"][0]["columns"]}
    assert cols["order_date"]["role"] == "time" and cols["order_id"]["role"] == "id" and r["files"][0]["kind"] == "events"
    assert c.post("/v1/analyze", headers=H, json={"analysis_id": "a1", "files": [{"name": "shop.csv", "path": str(tmp / "evil.csv")}], "use_ai": False}).status_code in (400, 404)
    assert c.post("/v1/analyze", headers=H, json={"analysis_id": "a1", "files": [{"name": "shop.csv", "path": "/etc/passwd"}], "use_ai": False}).status_code == 400
    assert c.post("/v1/analyze", headers=H, json={"analysis_id": "a1", "files": [{"name": "shop.csv", "path": str(up / "shop.csv")}], "use_ai": False}).status_code == 202
    j = wait(c, "a1")
    assert j["status"] == "done", j
    rep = c.get("/v1/reports/a1", headers=H).json()
    for k in ("briefing", "your_data", "insights", "intelligence", "questions", "limits", "reading"):
        assert k in rep
    assert rep["briefing"]["stories"] and rep["intelligence"]["fix"]
    kp = rep["your_data"][0]["kpis"][0]
    assert kp["unit"] == "" and kp["value"] > 0 and rep["your_data"][0]["breakdowns"] and rep["your_data"][0]["weekday"]
    f = rep["insights"]["findings"][0]
    assert f["rows"]["total"] > 0 and f["rows"]["rows"] and f["chart"]["values"]
    json.dumps(rep)                                          # fully JSON-safe
    assert (tmp / "data" / "analyses" / "a1" / "state.pkl.gz").exists()


def test_two_unlinked_files_and_a_summary_file(env):
    api, up, tmp = env
    a = pd.DataFrame({"sale_date": np.repeat(pd.date_range("2024-01-01", periods=100), 3), "amount": np.random.default_rng(1).normal(100, 5, 300)})
    a["region"] = ["N", "S", "E"] * 100
    b = pd.DataFrame({"Total Rows": [300], "Total Amount": ["$30,000"]})
    a.to_csv(up / "sales.csv", index=False); b.to_csv(up / "summary.csv", index=False)
    from alpha_engine import pipeline
    rep = pipeline.analyze("a2", [{"name": "sales.csv", "path": str(up / "sales.csv")}, {"name": "summary.csv", "path": str(up / "summary.csv")}], {}, str(tmp / "data"))
    kinds = {f["name"]: f["kind"] for f in rep["files"]}
    assert kinds == {"sales.csv": "events", "summary.csv": "summary"}
    assert "headline" in rep["briefing"]


def test_pipeline_with_investigation_and_ask(env):
    api, up, tmp = env
    make_files(up)
    from alpha_engine import pipeline
    from alpha_engine.llm import ScriptedProvider
    from alpha_engine.investigate.loop import make_investigator
    from alpha_engine.investigate.ask import ask
    answers = [{"action": "run", "why": "weekday check", "code": "result = df.groupby(df._t.dt.weekday).size()"}] 
    class Always(ScriptedProvider):
        def complete_json(self, system, payload):
            self.calls.append(payload)
            if not payload.get("results_so_far"):
                return {"action": "run", "why": "count rows", "code": "result = len(df)"}
            return {"action": "finish", "summary": "Row count was checked; the change lines up with the period shown in the numbers above."}
    prov = Always([])
    rep = pipeline.analyze("a3", [{"name": "shop.csv", "path": str(up / "shop.csv")}], {}, str(tmp / "data"), prov, investigate=make_investigator(prov, str(tmp / "data")))
    inv = [f for f in rep["insights"]["findings"] if f.get("investigation")]
    assert inv and inv[0]["investigation"]["verified"] and rep["ai"]["investigation"]["verified_summaries"] >= 1
    class A(ScriptedProvider):
        def complete_json(self, system, payload):
            if not payload["results_so_far"]:
                return {"action": "run", "why": "n", "code": "result = len(df)"}
            n = payload["results_so_far"][0]["result"]
            return {"action": "finish", "answer": f"There are {n} counted rows."}
    r = ask(A([]), str(tmp / "data"), "a3", "How many rows count?", rep)
    assert r["verified"] and "counted rows" in r["answer"]

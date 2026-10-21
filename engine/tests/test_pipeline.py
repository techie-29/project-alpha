import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from bench_business import make


@pytest.fixture()
def env(tmp_path, monkeypatch):
    up = tmp_path / "uploads"; up.mkdir()
    monkeypatch.setenv("ENGINE_UPLOAD_DIR", str(up)); monkeypatch.setenv("ENGINE_DATA_DIR", str(tmp_path / "data")); monkeypatch.setenv("ENGINE_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    import importlib, alpha_engine.api as api
    importlib.reload(api)
    return api, up, tmp_path


def write_business(up, days=240):
    files, truth = make(days=days, n_customers=600, n_products=40)
    specs = []
    for n, df in files.items():
        df.to_csv(up / n, index=False)
        specs.append({"name": n, "path": str(up / n)})
    return specs, files, truth


def wait(client, aid, tries=400):
    import time
    for _ in range(tries):
        j = client.get(f"/v1/jobs/{aid}", headers={"x-engine-key": "k"}).json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.5)
    raise AssertionError("timeout")


def test_end_to_end_through_the_api(env):
    api, up, tmp = env
    specs, files, truth = write_business(up)
    c = TestClient(api.app)
    H = {"x-engine-key": "k"}
    assert c.post("/v1/read", json={"files": specs, "use_ai": False}).status_code == 401
    r = c.post("/v1/read", headers=H, json={"files": specs, "use_ai": False}).json()
    roles = {f["name"]: f["role"] for f in r["files"]}
    assert roles["orders.csv"] == "transactions" and roles["stock.csv"] == "snapshot" and roles["products.csv"] == "master"
    cols = {x["name"]: x for x in next(f for f in r["files"] if f["name"] == "orders.csv")["columns"]}
    assert cols["order_total"]["concept"] == "revenue" and cols["order_date"]["type"] == "time"
    assert any(x["id"] == "stock_level" for x in r["concepts"]) and any(l["use"] for l in r["links"])
    assert c.post("/v1/analyze", headers=H, json={"analysis_id": "a1", "files": [{"name": "x.csv", "path": "/etc/passwd"}], "use_ai": False}).status_code == 400
    assert c.post("/v1/analyze", headers=H, json={"analysis_id": "a1", "files": specs, "use_ai": False}).status_code == 202
    j = wait(c, "a1")
    assert j["status"] == "done", j
    rep = c.get("/v1/reports/a1", headers=H).json()
    assert rep["version"] == 2
    for k in ("briefing", "overview", "insights", "suggestions", "coverage", "questions", "limits", "reading"):
        assert k in rep
    assert rep["overview"]["tiles"] and rep["overview"]["sections"] and rep["insights"]["items"]
    assert rep["briefing"]["headline"] and rep["briefing"]["key_numbers"]
    assert any(i["type"] == "stockout" for i in rep["insights"]["items"])
    json.dumps(rep)
    assert (tmp / "data" / "analyses" / "a1" / "state.pkl.gz").exists()


def test_confirmations_and_memory_change_the_reading(env):
    api, up, tmp = env
    specs, files, truth = write_business(up, days=120)
    from alpha_engine import pipeline
    r = pipeline.read(specs, {"concepts": {"orders.csv::order_cost": "expense"}}, None, memory={"ship_mode": "channel"})
    cols = {x["name"]: x for x in next(f for f in r["files"] if f["name"] == "orders.csv")["columns"]}
    assert cols["order_cost"]["concept"] == "expense" and cols["order_cost"]["source"] == "owner"
    assert cols["ship_mode"]["concept"] == "channel"


def test_owner_preferences_mute(env):
    api, up, tmp = env
    specs, files, truth = write_business(up, days=200)
    from alpha_engine import pipeline
    base = pipeline.analyze("p1", specs, {}, str(tmp / "data"))
    target = base["insights"]["items"][0]["pattern"]
    rep = pipeline.analyze("p2", specs, {}, str(tmp / "data"), preferences={target: "not_useful"})
    muted = [i for i in rep["insights"]["items"] if i["muted"]]
    assert muted and all(i["pattern"] == target for i in muted)
    assert not any(s["insight_id"] in {m["id"] for m in muted} for b in rep["suggestions"].values() for s in b)


def test_exports_v2(env):
    api, up, tmp = env
    specs, files, truth = write_business(up, days=200)
    from alpha_engine import pipeline
    from alpha_engine.report.export import to_pdf, to_xlsx
    import io, openpyxl
    rep = pipeline.analyze("e1", specs, {}, str(tmp / "data"))
    pdf = to_pdf(rep, {"answers": []})
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000
    wb = openpyxl.load_workbook(io.BytesIO(to_xlsx(rep)))
    assert {"Briefing", "Files", "Key numbers", "Insights", "Suggestions", "Chart data", "Coverage"} <= set(wb.sheetnames)
    assert wb["Insights"].max_row == 1 + len(rep["insights"]["items"])
    c = TestClient(api.app)
    assert c.post("/v1/export", headers={"x-engine-key": "k"}, json={"format": "pdf", "report": rep}).content[:4] == b"%PDF"

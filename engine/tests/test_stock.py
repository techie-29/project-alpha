"""A stock business end to end: item master (expiry dates, Excel + text dates), a movement ledger with five date styles,
monthly closing stock laid out as month columns, purchase orders (yyyymmdd, ISO with time zone), and a US-format daily summary.
The headline numbers must equal the raw truth and the planted problems must be found."""
import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from alpha_engine import pipeline
from alpha_engine.analyses import market
import bench_stock


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("stock")
    truth = bench_stock.make(str(d))
    files = [{"name": p.name, "path": str(p)} for p in sorted(d.iterdir())]
    rep = pipeline.analyze("stocktest", files, {}, str(tmp_path_factory.mktemp("data")), None)
    return rep, truth


def cols(rep, name):
    f = next(x for x in rep["reading"]["files"] if x["name"] == name)
    return f, {c["name"]: c for c in f["columns"]}


def test_columns_are_understood(run):
    rep, _ = run
    f, c = cols(rep, "stock_movements.csv")
    assert c["Movement"]["concept"] == "movement_type" and c["Qty"]["concept"] == "quantity" and f["role"] == "transactions"
    assert c["Txn Dt"]["date"]["order"] == "day-first" and c["Txn Dt"]["date"]["certain"]
    f, c = cols(rep, "purchase_orders.csv")
    assert c["Rate"]["concept"] == "unit_cost" and c["Qty Ordered"]["concept"] == "units_ordered" and c["Qty Received"]["concept"] == "units_received"
    assert c["Expected Date"]["concept"] == "due_date" and c["Received Date"]["concept"] == "done_date" and f["time_col"] == "Order Date"
    f, c = cols(rep, "Item Master.xlsx")
    assert c["Batch Expiry"]["concept"] == "expiry_date" and f["role"] == "master" and f["time_col"] is None
    f, c = cols(rep, "monthly_closing_stock.xlsx")
    assert f["role"] == "snapshot" and c["closing stock"]["concept"] == "stock_level" and any("months side by side" in n for n in f["notes"])
    f, c = cols(rep, "counter_daily_summary.csv")
    assert c["Day"]["date"]["order"] == "month-first" and c["Bills"]["concept"] == "activity_count"


def test_headline_numbers_match_the_raw_files(run):
    rep, truth = run
    tiles = {t["metric"]: t["value"] for p in [rep["overview"]] + (rep["overview"].get("parts") or []) for t in p.get("tiles", [])}
    assert tiles["stock_value"] == pytest.approx(truth["stock_value_latest"], abs=0.01)
    assert tiles["stock_units"] == truth["units_on_hand"]
    assert tiles["units"] == truth["units_sold"]
    assert tiles["out_of_stock"] == len(truth["zero_stock"])
    assert tiles.get("units_lost") == truth["damaged_units"]


def test_planted_problems_are_found(run):
    rep, truth = run
    items = rep["insights"]["items"]
    t = lambda kind: [i for i in items if i["type"] == kind]
    assert any("WH-Pune" in i["title"] for i in t("group_difference"))                      # 3x damage in one warehouse
    assert any("FastSupply" in i["title"] for i in t("group_difference"))                   # one supplier delivers late
    assert t("stockout") and t("stockout")[0]["numbers"]["items"] == len(truth["zero_stock"])
    assert t("dead_stock") and t("dead_stock")[0]["numbers"]["items"] == len(truth["dead"])
    exp = t("expiry")
    assert exp and exp[0]["numbers"]["items"] == len([x for x in truth["expiring_soon"] if x not in truth["zero_stock"]])
    assert any(i["type"] == "seasonality" and "Oct" in i["title"] for i in items)          # April-March business years still count
    assert not any("Average order value" in i["title"] for i in items)                      # a ledger has movements, not orders


def test_share_prices_are_levels_not_sums():
    rng = np.random.default_rng(1)
    d = pd.bdate_range("2020-01-01", periods=500)
    a = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, len(d))))
    a[200:260] *= np.linspace(1, 0.7, 60)                     # a fall
    a[260:] *= 0.7
    from alpha_engine.metrics.frame import Frame
    df = pd.DataFrame({"_t": d, "_ok": True, "price_level": a})
    F = Frame("p.csv", "periodic", None, df, True)
    out = market.run(F, "USD")
    kinds = {i["type"] for i in out}
    assert {"price_move", "drawdown"} <= kinds
    dd = next(i for i in out if i["type"] == "drawdown")
    assert dd["numbers"]["drawdown"] < -0.25

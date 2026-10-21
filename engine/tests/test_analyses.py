"""Planted patterns must be found; a business with nothing planted must stay quiet."""
import pytest
from _bench_frames import bench
from alpha_engine.analyses.run import run_all


@pytest.fixture(scope="module")
def found():
    files, truth, model, frames, links, pick, tables, views = bench()
    ins, checked = run_all(pick, {v.name: v for v in views})
    return ins, checked, truth


def titles(ins, kind=None):
    return [i["title"] for i in ins if kind is None or i["type"] == kind]


def test_planted_group_differences(found):
    ins = found[0]
    t = titles(ins, "group_difference")
    assert any("Returned rate" in x and "West" in x for x in t)
    assert any("margin" in x.lower() and "SALE10" in x for x in t)


def test_planted_interaction(found):
    t = titles(found[0], "combination")
    assert any("W3" in x and "Economy" in x for x in t)
    assert not any("East" in x for x in t)


def test_planted_trend_relationship_stock_and_loss(found):
    ins = found[0]
    assert any(i["type"] == "share_shift" and "Online" in i["title"] and "rose" in i["title"] for i in ins)
    assert any(i["type"] == "relationship" and "rating" in i["title"].lower() and "delay" in i["title"].lower() for i in ins)
    st = {i["type"]: i for i in ins if i["area"] == "stock"}
    assert st["stockout"]["numbers"]["items"] == 5 and st["dead_stock"]["numbers"]["items"] == 8
    assert any(i["type"] == "loss_makers" for i in ins)
    assert any(i["type"] == "concentration" for i in ins)


def test_every_insight_is_complete_and_labelled(found):
    for i in found[0]:
        assert i["title"] and i["detail"] and i["claim"] in ("Calculated", "Supported by evidence", "Possible (early sign)")
        assert i["polarity"] in ("good", "bad", "neutral")
    assert not found[1].get("failed"), found[1].get("failed")


def test_plain_business_stays_quiet():
    files, truth, model, frames, links, pick, tables, views = bench(seed=11, plant=False)
    ins, checked = run_all(pick, {v.name: v for v in views})
    tested = [i for i in ins if i["type"] in ("group_difference", "combination", "relationship", "trend", "share_shift", "seasonality", "weekday") and i["strength"] == "supported"]
    assert len(tested) <= 2, [i["title"] for i in tested]

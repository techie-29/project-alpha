import numpy as np
import pandas as pd
import pytest
from bench_business import make
from alpha_engine.understand.prepare import prepare
from alpha_engine.link.linker import find_links, build_views
from alpha_engine.model.build import build_model
from alpha_engine.metrics.frame import build_frame
from alpha_engine.overview.build import build_overview


@pytest.fixture(scope="module")
def biz():
    files, truth = make()
    tables = {}
    for n, df in files.items():
        df = df.copy(); df.insert(0, "_row", range(2, len(df) + 2))
        tables[n] = prepare(df, n)
    links = find_links(tables)
    model = build_model(tables, links)
    views, _, _ = build_views(tables, links)
    frames = {v.name: build_frame(v, model["files"][v.name]["columns"], model["files"][v.name]["file"], tables, links, model["files"]) for v in views if v.kind != "summary"}
    ov = build_overview(frames, {n: m["file"] for n, m in model["files"].items()}, links)
    return files, truth, model, frames, ov, links


def test_files_understood_as_one_business(biz):
    files, truth, model, frames, ov, links = biz
    roles = {f["name"]: f["role"] for f in ov["files"]}
    assert roles == {"orders.csv": "transactions", "order_items.csv": "lines", "products.csv": "master", "customers.csv": "master", "stock.csv": "snapshot"}
    c = {f: {k: v["concept"] for k, v in m["columns"].items()} for f, m in model["files"].items()}
    assert c["orders.csv"]["order_total"] == "revenue" and c["orders.csv"]["order_cost"] == "cost" and c["stock.csv"]["on_hand"] == "stock_level"
    assert c["order_items.csv"]["qty"] == "quantity" and c["products.csv"]["unit_cost"] == "unit_cost"
    used = {(l.child, l.parent) for l in links if l.use}
    assert ("order_items.csv", "products.csv") in used and ("orders.csv", "customers.csv") in used


def test_headline_numbers_match_the_raw_data(biz):
    files, truth, model, frames, ov, links = biz
    o = files["orders.csv"]
    ok = o[~o.status.isin(["Returned", "Cancelled"])]
    t = {x["metric"]: x for x in ov["tiles"]}
    assert t["revenue"]["value"] == pytest.approx(ok.order_total.sum(), rel=1e-9)
    assert t["orders"]["value"] == ok.order_id.nunique()
    assert t["customers"]["value"] == ok.customer_id.nunique()
    assert t["profit"]["value"] == pytest.approx((ok.order_total - ok.order_cost).sum(), rel=1e-9)
    assert t["margin"]["value"] == pytest.approx((ok.order_total - ok.order_cost).sum() / ok.order_total.sum(), rel=1e-9)
    s = files["stock.csv"]; last = s[s.snapshot_date == s.snapshot_date.max()]
    assert t["stock_units"]["value"] == last.on_hand.sum()
    val = (last.merge(files["products.csv"], on="product_id").eval("on_hand * unit_cost")).sum()
    assert t["stock_value"]["value"] == pytest.approx(val, rel=1e-9)
    assert t["out_of_stock"]["value"] == len(truth["out_of_stock"])
    assert "last_period" in t["revenue"] and "vs_last_year" in t["revenue"]


def test_sections_cover_every_area(biz):
    ov = biz[4]
    areas = {s["area"] for s in ov["sections"]}
    assert {"sales", "products", "customers", "operations", "service", "stock"} <= areas
    titles = [c["title"] for s in ov["sections"] for c in s["charts"]]
    assert "Revenue over time" in titles and "Top products" in titles and any("new and returning" in t for t in titles)
    assert any(t.startswith("Revenue by channel") for t in titles) and any("On-time rate" in t for t in titles)
    top = next(c for s in ov["sections"] for c in s["charts"] if c["title"] == "Top products")
    assert top["rows"][0]["name"].startswith("Product ")          # product names looked up from the product list

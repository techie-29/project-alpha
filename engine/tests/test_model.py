import numpy as np
import pandas as pd
from alpha_engine.understand.prepare import prepare
from alpha_engine.link.linker import find_links
from alpha_engine.model.build import build_model

R = np.random.default_rng(3)


def T(df, name):
    df = df.copy(); df.insert(0, "_row", range(2, len(df) + 2))
    return prepare(df, name)


def concepts(tables, links=None):
    m = build_model(tables, links or [])
    return {f: {c: v["concept"] for c, v in fm["columns"].items()} for f, fm in m["files"].items()}, m


def german_sales(n=800):
    menge = R.integers(1, 9, n); preis = R.choice([4.99, 12.5, 19.9, 49.0], n)
    betrag = np.round(menge * preis, 2); kosten = np.round(betrag * R.uniform(0.5, 0.8, n), 2)
    return pd.DataFrame({"Datum": pd.date_range("2024-01-01", periods=n, freq="7h").strftime("%d.%m.%Y"), "Kunde": [f"K-{i:05d}" for i in R.integers(1, 300, n)],
                         "Menge": menge, "Preis": preis, "Betrag": betrag, "Kosten": kosten, "Gewinn": np.round(betrag - kosten, 2),
                         "Kanal": R.choice(["Online", "Store", "Marketplace"], n), "Waehrung": "EUR"})


def test_foreign_headers_read_from_values_and_arithmetic():
    c, m = concepts({"verkauf.csv": T(german_sales(), "verkauf.csv")})
    f = c["verkauf.csv"]
    assert f["Menge"] == "quantity" and f["Preis"] == "unit_price" and f["Betrag"] == "revenue"
    assert f["Gewinn"] == "profit" and f["Kosten"] == "cost" and f["Kanal"] == "channel" and f["Waehrung"] == "currency"
    assert f["Kunde"] in ("customer_id",) or m["files"]["verkauf.csv"]["columns"]["Kunde"]["needs_confirmation"] or f["Kunde"].endswith("_id")
    assert any(i["text"] == "Menge x Preis = Betrag" or set(i["cols"]) == {"Menge", "Preis", "Betrag"} for i in m["files"]["verkauf.csv"]["identities"])


def test_meaningless_headers_still_read_through_arithmetic():
    n = 600
    a = R.integers(1, 12, n); b = R.choice([2.5, 7.25, 10.0, 99.99], n)
    df = pd.DataFrame({"d": pd.date_range("2024-01-01", periods=n, freq="5h"), "c1": a, "c2": b, "c3": np.round(a * b, 2)})
    c, _ = concepts({"x.csv": T(df, "x.csv")})
    assert c["x.csv"]["c1"] == "quantity" and c["x.csv"]["c2"] == "unit_price" and c["x.csv"]["c3"] == "revenue"


def test_stock_snapshot_is_a_level_and_products_are_a_master_list():
    dates = pd.date_range("2024-01-01", periods=30)
    skus = [f"SKU{i:03d}" for i in range(40)]
    snap = pd.DataFrame([(d, s, int(R.integers(0, 200))) for d in dates for s in skus], columns=["count_date", "sku", "units"])
    prods = pd.DataFrame({"sku": skus, "item": [f"Item {i}" for i in range(40)], "cost": np.round(R.uniform(2, 50, 40), 2), "category": R.choice(["A", "B", "C"], 40)})
    tables = {"inventory.csv": T(snap, "inventory.csv"), "products.csv": T(prods, "products.csv")}
    links = find_links(tables)
    c, m = concepts(tables, links)
    assert m["files"]["inventory.csv"]["file"]["role"] == "snapshot"
    assert c["inventory.csv"]["units"] == "stock_level"
    assert m["files"]["products.csv"]["file"]["role"] == "master" and m["files"]["products.csv"]["file"]["entity"] == "product"
    assert c["products.csv"]["cost"] == "unit_cost" and c["products.csv"]["sku"] == "product_id"


def test_owner_choice_wins_and_memory_helps():
    df = german_sales(300)
    p = T(df, "v.csv")
    m = build_model({"v.csv": p}, [], {"concepts": {"v.csv::Kosten": "expense"}})
    assert m["files"]["v.csv"]["columns"]["Kosten"]["concept"] == "expense" and m["files"]["v.csv"]["columns"]["Kosten"]["source"] == "owner"
    df2 = df.rename(columns={"Kanal": "zz_kind"})
    m2 = build_model({"v.csv": T(df2, "v.csv")}, [], None, memory={"zz_kind": "channel"})
    assert m2["files"]["v.csv"]["columns"]["zz_kind"]["concept"] == "channel"


def test_personal_columns_are_kept_out():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=200, freq="D"), "customer_name": [f"Person {i}" for i in range(200)],
                       "email": [f"p{i}@x.com" for i in range(200)], "campaign_name": R.choice(["Spring", "Diwali", "Summer"], 200), "amount": R.uniform(5, 99, 200).round(2)})
    c, _ = concepts({"s.csv": T(df, "s.csv")})
    assert c["s.csv"]["customer_name"] == "personal" and c["s.csv"]["email"] == "personal" and c["s.csv"]["campaign_name"] != "personal"

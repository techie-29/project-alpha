import numpy as np
import pandas as pd
from alpha_engine.understand.prepare import prepare
from alpha_engine.link.linker import find_links, build_views, apply_link_confirmations


def shop():
    rng = np.random.default_rng(5)
    n = 900
    orders = pd.DataFrame({
        "order_id": [f"ORD-{i:05d}" for i in range(n)],
        "order_date": pd.date_range("2025-01-01", periods=n // 3, freq="D").repeat(3).strftime("%Y-%m-%d"),
        "customer_id": [f"CUST-{i % 150:04d}" for i in range(n)],
        "order_status": rng.choice(["Completed", "Cancelled"], n, p=[.9, .1]),
        "net_sales": rng.normal(200, 20, n).round(2),
    })
    k = 2700
    items = pd.DataFrame({
        "order_id": rng.choice(orders.order_id, k),
        "product_id": [f"PROD-{i % 120:04d}" for i in range(k)],
        "quantity": rng.integers(1, 5, k),
        "net_sales": rng.normal(70, 8, k).round(2),
    })
    customers = pd.DataFrame({"customer_id": [f"CUST-{i:04d}" for i in range(150)], "segment": rng.choice(["A", "B", "C"], 150)})
    products = pd.DataFrame({"product_id": [f"PROD-{i:04d}" for i in range(120)], "product_category": rng.choice(["Phones", "TVs", "Laptops"], 120)})
    out = {}
    for nm, d in dict(orders=orders, order_items=items, customers=customers, products=products).items():
        d["_row"] = d.index + 2
        out[nm] = prepare(d, nm)
    return out


def test_links_found_with_right_direction_and_unrelated_ignored():
    t = shop()
    links = find_links(t)
    keys = {l.key: l for l in links}
    assert "order_items.order_id|orders.order_id" in keys and keys["order_items.order_id|orders.order_id"].use
    assert "orders.customer_id|customers.customer_id" in keys
    assert "order_items.product_id|products.product_id" in keys
    assert not any({l.child, l.parent} == {"customers", "products"} for l in links)


def test_chance_match_of_small_numbers_is_not_used():
    a = pd.DataFrame({"row_no": range(1, 60), "x": 1.0}); b = pd.DataFrame({"code_ref": range(1, 60), "y": 2.0})
    for d in (a, b): d["_row"] = d.index + 2
    t = {"a": prepare(a, "a"), "b": prepare(b, "b")}
    assert not any(l.use for l in find_links(t))


def test_views_borrow_dates_inherit_exclusions_and_never_multiply_rows():
    t = shop()
    links = find_links(t)
    views, notes, warns = build_views(t, links)
    by = {v.name: v for v in views}
    items = by["order_items"]
    assert len(items.df) == 2700                                   # rows never multiply
    assert items.kind == "events" and items.time_col == "order_date"
    assert "product_category" in items.slices and "segment" in items.slices and "order_status" in items.slices
    cancelled = t["orders"].df.set_index("order_id")["order_status"]
    expected_ok = ~items.df["order_id"].map(cancelled).eq("Cancelled")
    assert (items.ok == expected_ok).all()                         # cancelled order => its items do not count
    assert by["customers"].kind == "dimension" and by["products"].kind == "dimension"
    assert any("dates are looked up" in n for n in notes)


def test_owner_can_reject_a_link():
    t = shop()
    links = apply_link_confirmations(find_links(t), {"orders.customer_id|customers.customer_id": False})
    views, _, _ = build_views(t, links)
    assert "customers" in {v.name for v in views} and {v.name: v for v in views}["customers"].kind != "dimension"


def test_independent_files_stay_independent():
    a = pd.DataFrame({"sale_date": pd.date_range("2025-01-01", periods=120).strftime("%Y-%m-%d"), "amount": np.arange(120) * 1.0}); a["_row"] = a.index + 2
    b = pd.DataFrame({"visit_date": pd.date_range("2025-01-01", periods=120).strftime("%Y-%m-%d"), "visits": np.arange(120) * 2.0}); b["_row"] = b.index + 2
    t = {"sales": prepare(a, "sales"), "web": prepare(b, "web")}
    assert find_links(t) == []
    views, _, _ = build_views(t, [])
    assert [v.name for v in views] == ["sales", "web"]

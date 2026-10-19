import numpy as np
import pandas as pd
from alpha_engine.understand.roles import profile_columns, apply_owner_confirmations
from alpha_engine.understand.ai_review import review_columns, describe_column
from alpha_engine.llm import FakeProvider, NullProvider


def frame(n=400):
    rng = np.random.default_rng(1)
    d = pd.DataFrame({
        "order_date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
        "order_time": [f"{h % 24:02d}:{(h * 7) % 60:02d}:11" for h in range(n)],
        "customer_postal_code": rng.integers(10000, 99999, n),
        "phone": [f"+91 9{rng.integers(10**8, 10**9)}" for _ in range(n)],
        "customer_id": [f"CUST-{i % 120:06d}" for i in range(n)],
        "rating": rng.integers(1, 6, n),
        "month": rng.integers(1, 13, n),
        "quantity": rng.integers(1, 9, n),
        "net_sales": rng.normal(100, 20, n).round(2),
        "is_repeat_customer": rng.random(n) > 0.5,
        "amount_text": [f"${x:,.2f}" for x in rng.normal(500, 50, n)],
        "refund": [f"({x})" if i % 9 == 0 else str(x) for i, x in enumerate(rng.integers(1, 99, n))],
        "customer_name": [f"Person Number {i} Smith" for i in range(n)],
        "coupon_code": rng.choice(["A10", "B20", "C30", None], n),
        "row_number": np.arange(1, n + 1),
        "same": ["x"] * n,
    })
    d["_row"] = d.index + 2
    return d


def test_tricky_columns_get_the_right_role():
    r = profile_columns(frame())
    assert r["order_date"]["role"] == "time"
    assert r["order_time"]["role"] == "time_of_day"          # never a calendar date
    assert r["customer_postal_code"]["role"] == "id"          # a number, but never added up
    assert r["phone"]["role"] == "id"
    assert r["customer_id"]["role"] == "id"
    assert r["rating"]["role"] == "measure" and "category" in r["rating"]["secondary"]
    assert r["month"]["role"] == "category" and r["month"]["period_part"] == "month"
    assert r["quantity"]["role"] == "measure"
    assert r["net_sales"]["role"] == "measure"
    assert r["is_repeat_customer"]["role"] == "flag"
    assert r["amount_text"]["role"] == "measure"             # "$1,234.50" cleaned
    assert r["refund"]["role"] == "measure"                  # "(5)" means negative
    assert r["customer_name"]["role"] == "text"
    assert r["coupon_code"]["role"] == "category"            # code header, but few values
    assert r["row_number"]["role"] == "id"
    assert r["same"]["role"] == "constant"


def test_measure_that_is_really_ids_is_vetoed():
    d = pd.DataFrame({"weird": np.arange(1000, 1400), "_row": np.arange(2, 402)})
    r = profile_columns(d)
    assert r["weird"]["role"] == "id"


def test_every_decision_has_reasons_and_confidence():
    for c, i in profile_columns(frame()).items():
        assert 0 <= i["confidence"] <= 1 and isinstance(i["reasons"], list)


def test_ambiguous_dates_are_flagged_not_silent():
    d = pd.DataFrame({"when_date": ["04/05/2026", "03/06/2026", "01/02/2026"] * 40, "_row": range(2, 122)})
    i = profile_columns(d)["when_date"]
    assert i["role"] == "time" and i["date_order"] == "ambiguous->day-first" and i["needs_confirmation"]


def test_owner_confirmation_wins():
    r = profile_columns(frame())
    apply_owner_confirmations(r, {"rating": "category"})
    assert r["rating"]["role"] == "category" and r["rating"]["confidence"] == 1.0 and not r["rating"]["needs_confirmation"]


def unsure_frame():
    df = frame()
    df["when_date"] = ["04/05/2026", "03/06/2026", "01/02/2026", "07/08/2026"] * (len(df) // 4)
    return df


def test_ai_is_asked_only_about_unsure_columns_and_never_sees_rows():
    df = unsure_frame()
    roles = profile_columns(df)
    fake = FakeProvider({"columns": {"when_date": {"role": "time", "reason": "looks like a date"}}})
    status = review_columns(df, roles, fake)
    assert [c["name"] for c in fake.calls[0]["unsure"]] == ["when_date"]   # confident columns are not sent
    for q in fake.calls:
        text = str(q)
        assert "Person Number" not in text and "+91" not in text and "CUST-" not in text
    assert status["status"] == "ok"


def test_ai_proposal_is_vetted_by_code():
    d = pd.DataFrame({"zip_label": ["ab1", "cd2", "ef3"] * 100, "_row": range(2, 302)})
    roles = profile_columns(d)
    roles["zip_label"]["needs_confirmation"] = True
    review_columns(d, roles, FakeProvider({"columns": {"zip_label": {"role": "measure", "reason": "amount"}}}))
    assert roles["zip_label"]["ai"]["accepted"] is False       # text can't be a measure


def test_ai_outage_never_breaks_the_engine():
    df = unsure_frame()
    roles = profile_columns(df)
    assert "unavailable" in review_columns(df, roles, FakeProvider(fail=True))["status"]
    assert "unavailable" in review_columns(df, roles, NullProvider())["status"]


def test_describe_column_shares_no_examples_for_personal_headers():
    df = frame()
    roles = profile_columns(df)
    assert "example_values" not in describe_column(df, "customer_name", roles["customer_name"])


def test_blank_means_no_flag_and_small_tables_keep_their_groups():
    n = 600
    d = pd.DataFrame({
        "return_status": ["Returned" if i % 14 == 0 else None for i in range(n)],
        "brand": [f"Brand {i % 70}" for i in range(n)],            # 70 repeated labels in a 600-row table
        "product_name": [f"Gadget model {i} deluxe" for i in range(n)],
        "_row": range(2, n + 2),
    })
    r = profile_columns(d)
    assert r["return_status"]["role"] == "flag" and r["return_status"]["presence"] is True
    assert r["brand"]["role"] == "category"
    assert r["product_name"]["role"] == "text"

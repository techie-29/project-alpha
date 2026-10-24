"""Dates the way real exports write them: every common style, mixed styles in one column, day/month order from evidence."""
import datetime as dt
import numpy as np
import pandas as pd
from alpha_engine.understand.dates import read_dates, header_period, unpivot_periods, unpivot_tickers
from alpha_engine.understand.roles import profile_columns
from alpha_engine.understand.prepare import prepare


def rd(vals, name="date", **k):
    return read_dates(pd.Series(vals, dtype=object), name, **k)


def ymd(r):
    return list(r.parsed.dt.strftime("%Y-%m-%d").fillna("NaT"))


def test_mixed_styles_in_one_column():
    r = rd(["01-Apr-23", "01.04.2023 20:06", "01/04/2023", "45017", "2023-04-02", "13/04/2023", "", "N/A"], "Txn Dt")
    assert r.order == "day-first" and r.certain
    assert ymd(r)[:6] == ["2023-04-01"] * 4 + ["2023-04-02", "2023-04-13"]
    assert r.junk == 2 and r.rate == 1.0
    assert r.parsed.iloc[1].hour == 20


def test_month_first_from_a_day_above_12():
    r = rd(["04/15/2024", "04/16/2024", "05/01/2024"])
    assert r.order == "month-first" and r.certain and ymd(r) == ["2024-04-15", "2024-04-16", "2024-05-01"]


def test_ambiguous_order_is_a_judgement_and_says_so():
    r = rd(["04/05/2026", "03/06/2026", "01/02/2026"] * 10)
    assert r.order == "day-first" and not r.certain


def test_monthly_figures_dated_on_the_first():
    r = rd(["01/04/2024", "01/05/2024", "01/06/2024", "01/07/2024"])
    assert ymd(r) == ["2024-04-01", "2024-05-01", "2024-06-01", "2024-07-01"] and not r.certain


def test_owner_order_wins():
    r = rd(["01/04/2024", "01/05/2024", "01/06/2024"], order="month-first")
    assert ymd(r) == ["2024-01-04", "2024-01-05", "2024-01-06"] and r.certain


def test_timezones_compact_and_excel_numbers():
    r = rd(["2023-04-12T10:15:00+05:30", "2023-04-13T09:00:00Z", ""], "Received Date")
    assert ymd(r)[:2] == ["2023-04-12", "2023-04-13"] and r.parsed.iloc[0].hour == 10
    assert ymd(rd([20240415, 20240416, 20240501], "Order Date")) == ["2024-04-15", "2024-04-16", "2024-05-01"]
    assert rd([20240415, 20240416, 20240501], "Qty") is None            # numbers are only dates when the header says so
    assert ymd(rd([45017, 45018], "Invoice Date")) == ["2023-04-01", "2023-04-02"]


def test_periods_weeks_quarters_financial_years():
    assert ymd(rd(["Jan-24", "Feb-24", "Mar-24"], "Month")) == ["2024-01-01", "2024-02-01", "2024-03-01"]
    assert ymd(rd(["Q1 2024", "Q2 2024", "2024-Q3"])) == ["2024-01-01", "2024-04-01", "2024-07-01"]
    assert ymd(rd(["2024-W03", "2024-W04"])) == ["2024-01-15", "2024-01-22"]
    assert ymd(rd(["FY 2023-24", "FY24"])) == ["2023-04-01", "2023-04-01"]
    assert rd(["Q1 2024", "Q2 2024", "Q3 2024"]).grain == "quarter"


def test_written_months_weekdays_and_excel_cells():
    assert ymd(rd(["Monday, January 15, 2024", "Tuesday, 16th January 2024"])) == ["2024-01-15", "2024-01-16"]
    assert ymd(rd([dt.datetime(2024, 1, 5), "15-Jan-23", dt.datetime(2024, 2, 1)], "Added On")) == ["2024-01-05", "2023-01-15", "2024-02-01"]
    r = rd(["5/4/24 2:30 PM", "6/4/24 11:00 AM", "13/4/24 12:15 AM"])
    assert ymd(r) == ["2024-04-05", "2024-04-06", "2024-04-13"] and r.parsed.iloc[0].hour == 14 and r.parsed.iloc[2].hour == 0


def test_not_dates():
    assert rd(["apple", "banana"]) is None
    assert rd([1.5, 2.5, 3.5], "price") is None


def test_sibling_column_settles_the_order():
    n = 60
    df = pd.DataFrame({"order_date": ["13/0%d/2024" % (i % 9 + 1) for i in range(n)],
                       "ship_date": ["0%d/0%d/2024" % (i % 9 + 1, (i + 3) % 9 + 1) for i in range(n)], "_row": range(2, n + 2)})
    r = profile_columns(df)
    assert r["order_date"]["date_order"] == "day-first" and r["order_date"]["date_certain"]
    assert r["ship_date"]["date_order"] == "day-first" and "another date column" in r["ship_date"]["date_reason"]


def test_expiry_dates_are_not_the_timeline():
    n = 120
    df = pd.DataFrame({"Item": [f"I{i % 30}" for i in range(n)], "Batch Expiry": pd.date_range("2027-01-01", periods=n).strftime("%d/%m/%Y"),
                       "Qty": np.arange(n) % 7 + 1, "_row": range(2, n + 2)})
    p = prepare(df, "batches.csv")
    assert p.time_col is None and any("expiry" in x for x in p.notes)


def test_wide_month_columns_become_rows():
    df = pd.DataFrame({"Item Code": ["A", "B"], "Item Name": ["x", "y"], "Apr-2023": [1, 2], "May-2023": [3, 4], "Jun-2023": [5, 6]})
    long, note = unpivot_periods(df, "monthly_closing_stock.xlsx")
    assert note and len(long) == 6 and "closing stock" in long.columns and "Month" in long.columns
    assert long["Month"].min() == pd.Timestamp("2023-04-01")
    assert header_period("Q3 2024")[1] == "quarter" and header_period("Item Name") is None


def test_wide_share_prices_become_rows():
    df = pd.DataFrame({"MSFT": [1.0, 2.0, 3.0], "IBM": [4.0, 5.0, 6.0], "AAPL": [7.0, 8.0, 9.0], "Date": ["2024-01-01", "2024-01-02", "2024-01-03"]})
    long, note = unpivot_tickers(df)
    assert note and set(long.columns) == {"Date", "Symbol", "Price"} and len(long) == 9
    same, n2 = unpivot_tickers(pd.DataFrame({"Date": ["2024-01-01"] * 3, "Qty": [1, 2, 3], "MRP": [4, 5, 6]}))
    assert n2 is None

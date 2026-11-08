from datetime import date

import numpy as np

from alpha_engine.overview.forecast import make_forecast

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def series(n, f, start_year=2024):
    x, y = [], []
    for i in range(n):
        x.append(f"{MONTHS[i % 12]} {start_year + i // 12}")
        y.append(f(i))
    return x, y


def end_of(x):
    mon, yr = x[-1].split()
    m = MONTHS.index(mon) + 1
    return date(int(yr), m, [31, 29 if int(yr) % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])


def test_too_little_history_gives_no_forecast():
    x, y = series(5, lambda i: 100 + i)
    f = make_forecast(x, y, end_of(x))
    assert f["status"] == "none" and "Not enough history" in f["reason"]


def test_incomplete_last_month_is_left_out():
    x, y = series(8, lambda i: 100 + i)
    f = make_forecast(x, y, date(2024, 8, 10))                      # data stops on 10 Aug: Aug is partial
    assert f["status"] == "ok" and f["history_months"] == 7 and f["x"][0] == "Aug 2024"


def test_steady_growth_is_continued_and_tested_against_the_past():
    x, y = series(18, lambda i: 1000 + 30 * i)
    f = make_forecast(x, y, end_of(x))
    assert f["status"] == "ok" and f["x"] == ["Jul 2025", "Aug 2025", "Sep 2025"]
    assert f["mid"][0] > y[-1] * 0.95 and f["mid"][0] < y[-1] * 1.12
    assert f["backtest"]["grade"] == "good" and f["backtest"]["error"] < 0.05
    assert all(lo <= m <= hi for lo, m, hi in zip(f["low"], f["mid"], f["high"]))


def test_a_repeating_season_is_learned_with_two_years():
    pattern = [1.0, 0.9, 0.95, 1.0, 1.05, 1.0, 0.9, 0.9, 1.0, 1.4, 1.5, 1.3]
    x, y = series(24, lambda i: 1000 * pattern[i % 12])
    f = make_forecast(x, y, end_of(x))                              # next months are Jan, Feb, Mar of year 3
    assert f["seasonal"] and abs(f["mid"][0] - 1000) < 120


def test_short_series_says_it_could_not_be_tested():
    x, y = series(7, lambda i: 500 + 10 * i)
    f = make_forecast(x, y, end_of(x))
    assert f["status"] == "ok" and f["backtest"] is None and "Not enough history to test" in f["untested"]


def test_chaotic_history_is_withheld():
    rng = np.random.default_rng(3)
    x, y = series(14, lambda i: float(rng.choice([100, 900, 50, 1200, 300])))
    f = make_forecast(x, y, end_of(x))
    assert f["status"] == "none" and "unpredictable" in f["reason"]

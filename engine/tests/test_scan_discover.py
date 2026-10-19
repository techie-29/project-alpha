"""Benchmarks with known truth. These are the proof that the scan finds real changes and stays quiet on quiet data."""
import numpy as np
import pytest
from bench import business
from alpha_engine.understand.prepare import prepare
from alpha_engine.scan.engine import scan_view
from alpha_engine.scan.stats import run_tests, bh
from alpha_engine.discover.discover import discover


def run(df, name="shop"):
    sr = scan_view(prepare(df, name))
    return sr, discover(sr)


def test_planted_changes_are_found_with_the_right_driver():
    sr, d = run(business(1, years=3))
    titles = " | ".join(f["title"] for f in d["findings"])
    assert "Laptop X" in titles and "unusually low from 02 Sep 2024" in titles          # 4-week sales collapse
    ret = next(f for f in d["findings"] if "Returned" in f["title"] and f["slice_col"] is None)
    assert ret["level"] == "confirmed" and ret["polarity"] == "bad"
    top = ret["drivers"]["by_column"][0]
    assert top["col"] == "city" and top["top"][0]["value"] == "Pune" and top["top"][0]["surprise"] > 3
    assert ret["drivers"]["explained"] > 0.8
    assert ret["numbers"]["exposure"] > 0 and len(ret["folded"]) >= 1                      # slice findings fold into it


def test_collapse_also_found_with_only_two_years():
    _, d = run(business(1, years=2))
    assert any("Laptop X" in f["title"] and "02 Sep 2024" in f["title"] for f in d["findings"])


def test_quiet_businesses_rarely_raise_a_confirmed_alarm():
    bad = 0
    for s in range(300, 312):
        _, d = run(business(s, years=3, planted=False, seasonal=(s % 2 == 0)))
        bad += any(f["level"] == "confirmed" for f in d["findings"])
    assert bad <= 2, f"{bad}/12 quiet businesses had a confirmed false alarm"


def test_real_growth_trend_is_found():
    _, d = run(business(9, years=3, planted=False, seasonal=False, drift=True))
    assert any(f["test"] == "trend" and f["slice_col"] is None and f["direction"] == "up" and f["level"] == "confirmed" for f in d["findings"])


def test_yearly_repeat_is_called_seasonal_not_a_change():
    sr, d = run(business(4, years=2, planted=False, seasonal=True))
    confirmed_windows = [f for f in d["findings"] if f["level"] == "confirmed" and f["test"] in ("window", "shift") and f["slice_col"] is None]
    assert len(d["seasonal"]) >= 1 or not confirmed_windows


def test_duplicate_measures_and_identical_slices_are_not_double_counted():
    sr, _ = run(business(1, years=2))
    assert any("moves with" in x for x in sr.dropped_duplicates)


def test_stat_primitives_are_calibrated_on_quiet_series():
    rng = np.random.default_rng(11)
    hits = sum(any(r["p"] < 0.01 for r in run_tests(rng.normal(100, 10, 104))) for _ in range(150))
    assert hits <= 12                                          # nominal ~4 tests x 1% = ~4%; allow slack
    q = bh(np.array([0.001, 0.01, 0.04, 0.5, 0.9]))
    assert q[0] <= 0.005 and q[-1] <= 1.0 and np.all(np.diff(q[np.argsort([0.001, 0.01, 0.04, 0.5, 0.9])]) >= -1e-12)


def test_thin_series_can_only_be_early_signs():
    sr, d = run(business(1, years=3))
    for l in sr.leads:
        if l.get("sparse"):
            assert l["level"] == "early"


def test_snapshot_mode_for_files_without_dates():
    import pandas as pd
    rng = np.random.default_rng(2)
    n = 900
    df = pd.DataFrame({"segment": rng.choice(["A", "B", "C"], n), "spend": rng.normal(100, 10, n)})
    df.loc[df.segment == "C", "spend"] += 25
    df["_row"] = df.index + 2
    from alpha_engine.scan.snapshot import snapshot
    s = snapshot(prepare(df, "customers"))
    assert s and s["findings"][0]["groups"][0]["value"] == "C" and "not a trend" in s["findings"][0]["claim"]

"""The strict checker: true numbers (as people write them) pass; made-up numbers do not."""
import numpy as np
from alpha_engine.investigate.verifier import verify_strict, verify

RES = {"by": ["year"], "rows": [{"group": "2010", "value": 0.1402}, {"group": "2011", "value": 0.1561}, {"group": "2012", "value": 0.1213}, {"group": "2013", "value": 0.0621}],
       "overall": 0.1134, "rows_used": 2534}
SALES = {"rows": [{"group": "Sliced Pineapple", "value": 214500.0, "margin": 0.014}, {"group": "Jams", "value": 98000.0, "margin": -0.008}], "overall": 2515308.5}


def test_true_numbers_written_normally_pass():
    for t in ["Margin fell from 14.0% in 2010 to 6.2% in 2013.", "Margin was 11.3% overall across 2,534 rows.",
              "It fell 7.8 points between 2010 and 2013.", "That is a 56% drop in margin.", "Sliced Pineapple brought 2.1 lakh of sales at a 1.4% margin.",
              "Total sales were 2.5M.", "Jams run at -0.8%."]:
        ok, why = verify_strict(t, [RES, SALES])
        assert ok, (t, why)


def test_numbers_from_other_results_or_made_up_fail():
    assert not verify_strict("Margin fell to 4.9% in 2013.", [RES])[0]
    assert not verify_strict("Sliced Pineapple brought 2.1 lakh of sales.", [RES])[0]      # true, but not in what it cites
    assert not verify_strict("Margin fell because of discounts: 14.0%.", [RES])[0]          # causal wording


def test_random_percentages_are_mostly_refused():
    rng = np.random.default_rng(0)
    ok_new = 0
    n = 400
    for _ in range(n):
        v = round(float(rng.uniform(0.5, 60)), 1)
        t = f"The share reached {v}% last year."
        ok_new += verify_strict(t, [RES])[0]
    assert ok_new / n <= 0.15, ok_new / n


def test_hyphenated_points_and_sums_of_two_values():
    r = {"overall": 0.07, "rows": [{"group": "High", "value": -0.0039, "n": 400}, {"group": "Medium", "value": 0.0938, "n": 600}]}
    q = {"rows": [{"group": "HP", "value": -14563.71}, {"group": "RJ", "value": -14135.88}]}
    assert verify_strict("High margin is -0.39% vs Medium 9.38%, a 9.77-point gap.", [r])[0]
    assert not verify_strict("High margin is -0.39% vs Medium 9.38%, a 9.9-point gap.", [r])[0]
    assert verify_strict("They lose 28,699.59 together.", [q])[0]
    assert not verify_strict("They lose 28,999.59 together.", [q])[0]
    assert not verify_strict("It is 99.9% better.", [r])[0]

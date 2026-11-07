"""Headers that used to be read wrongly: person details, towns, and look-alike words (age/agent, mobile orders, e-mail opt-in)."""
import numpy as np
import pandas as pd
from alpha_engine import pipeline


def _concepts(tmp_path, data):
    path = tmp_path / "t.csv"
    pd.DataFrame(data).to_csv(path, index=False)
    r = pipeline.read([{"name": "t.csv", "path": str(path)}], {})
    return {c["name"]: c["concept"] for c in r["files"][0]["columns"]}


def test_person_details_town_and_lookalikes(tmp_path):
    rng = np.random.default_rng(1); n = 150
    got = _concepts(tmp_path, {
        "Full Name": [f"Person {i}" for i in range(n)], "E-mail": [f"p{i}@x.com" for i in range(n)], "Years": rng.integers(18, 70, n),
        "town": rng.choice(["Pune", "Delhi", "Mumbai"], n), "Phone No": [f"98{rng.integers(10**7, 10**8)}" for _ in range(n)],
        "Email Opt In": rng.choice(["Yes", "No"], n), "Mobile Orders": rng.integers(0, 50, n), "Name": rng.choice(["Pen", "Book", "Bag", "Cup"], n),
        "Customer Age": rng.integers(18, 80, n)})
    assert got["Full Name"] == "personal" and got["E-mail"] == "personal" and got["Phone No"] == "personal"
    assert got["town"] == "location"
    assert got["Email Opt In"] == "yes_no"            # not personal data
    assert got["Mobile Orders"] == "number"
    assert got["Name"] == "name_label"                # a few repeated names: products, not people
    assert got["Years"] == "age" and got["Customer Age"] == "age"


def test_profile_headers_land_in_categories_the_analysis_can_use(tmp_path):
    rng = np.random.default_rng(3); n = 200
    got = _concepts(tmp_path, {
        "cust_id": range(n), "sex": rng.choice(["M", "F"], n), "dob": pd.date_range("1960-01-01", periods=n, freq="40D").strftime("%Y-%m-%d"),
        "fax": [f"022-{rng.integers(10**6, 10**7)}" for _ in range(n)], "marital_status": rng.choice(["Single", "Married", "Divorced"], n),
        "occupation": rng.choice(["Teacher", "Engineer", "Doctor", "Trader"], n), "priority": rng.choice(["High", "Medium", "Low"], n),
        "team": rng.choice(["North", "South", "East"], n), "month": rng.choice(["Jan", "Feb", "Mar"], n), "hobby": rng.choice(["Chess", "Golf", "Art"], n),
        "amount": rng.integers(100, 5000, n), "order_date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d")})
    assert got["sex"] == "gender" and got["dob"] == "birth_date" and got["fax"] == "personal"
    assert got["marital_status"] == "demographic" and got["occupation"] == "demographic"
    assert got["priority"] == "priority_level" and got["team"] == "team_role" and got["month"] == "period_label"
    assert got["hobby"] == "group"                      # unknown header: still a way to split results, never left out

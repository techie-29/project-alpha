"""The cleaning step on a small, deliberately broken customer file: every planted problem must be found."""
import pandas as pd
from alpha_engine import pipeline

ROWS = [
    [1, "Rahul", "rahul.example.com", 34, "Mumbai", "2024-01-05", 1200],
    [2, "Samira", "samira@x.com", 29, "Delhi", "2024-02-11", 800],
    [2, "Samira", "samira@x.com", 29, "Delhi", "2024-02-11", 800],
    [3, "Anil", "anil@x.com", -5, "bengaluru", "2024-03-02", 950],
    [4, "Meera", "meera@x.com", 150, "Bengaluru", "2024-03-15", "1O00"],
    [5, "Kiran", "kiran@x.com", "twenty", "Pune", "2026-13-09", 700],
    [6, "Dev", "dev@x.com", None, "Chennai", "not-a-date", 650],
    [7, "Isha", "isha@x.com", 41, None, "2024-05-20", -300],
    [8, "Tara", "tara@x.com", 38, "Bengaluru", "2024-06-01", 1100],
    [9, "Omar", "omar@x.com", 45, "Mumbai", "2024-06-12", 900],
    [10, "Lena", "lena@x.com", 52, "Delhi", "2024-07-03", 1500],
    [11, "Ravi", "ravi@x.com", 27, "Pune", "2024-07-19", 1000],
]
COLS = ["customer_id", "name", "email", "age", "city", "signup_date", "amount"]


def _quality(tmp_path, **conf):
    path = tmp_path / "corrupted_customers.xlsx"
    pd.DataFrame(ROWS, columns=COLS).to_excel(path, index=False)
    return pipeline.quality([{"name": "corrupted_customers.xlsx", "path": str(path)}], conf)["files"][0]


def test_planted_problems_are_all_found(tmp_path):
    rep = _quality(tmp_path)
    assert len(rep["auto"]) == 3                                   # repeated row, spelling, letter O typed for zero
    kinds = {g["type"] for g in rep["groups"]}
    assert {"impossible_value", "not_a_number", "invalid_date", "missing", "invalid_email", "negative_value"} <= kinds
    assert rep["summary"]["decisions"] == 9
    assert rep["summary"]["rows_before"] == 12 and rep["summary"]["rows_after"] == 11


def test_owner_choice_changes_the_result(tmp_path):
    rep = _quality(tmp_path, fixes={"*": {"impossible_value": "remove"}})
    assert rep["summary"]["rows_after"] < 11
    assert next(g for g in rep["groups"] if g["type"] == "impossible_value")["choice"] == "remove"

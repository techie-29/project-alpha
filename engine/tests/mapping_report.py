"""Print how many labelled columns the engine reads correctly. Run from the engine folder:  python tests/mapping_report.py"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mapping_cases import cases                      # noqa: E402
from alpha_engine.understand.prepare import prepare  # noqa: E402
from alpha_engine.model.build import build_model     # noqa: E402


def score(verbose: bool = True) -> tuple[int, int, list]:
    ok = total = 0
    misses = []
    for name, df, exp in cases():
        d = df.copy(); d.insert(0, "_row", range(2, len(d) + 2))
        p = prepare(d, name)
        m = build_model({name: p}, [])
        cols = m["files"][name]["columns"]
        for col, want in exp.items():
            got = cols.get(col, {}).get("concept")
            if col == p.time_col and got is None:
                got = "event_date"
            good = got in want if isinstance(want, set) else got == want
            total += 1; ok += good
            if not good:
                misses.append((name, col, want, got))
    if verbose:
        for m in misses:
            print(f"  MISS {m[0]:28s} {m[1]:26s} want {str(m[2]):30s} got {m[3]}")
        print(f"{ok}/{total} correct ({ok / total:.0%})")
    return ok, total, misses


if __name__ == "__main__":
    score()

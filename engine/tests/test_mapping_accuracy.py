"""Column reading measured on labelled files from many kinds of business (see mapping_cases / mapping_holdout / mapping_blind)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapping_report                                   # noqa: E402
import mapping_cases, mapping_holdout, mapping_blind    # noqa: E402


def _score(mod):
    mapping_report.cases = mod.cases
    return mapping_report.score(verbose=False)


def test_accuracy_on_all_labelled_sets():
    ok = total = 0
    for mod in (mapping_cases, mapping_holdout, mapping_blind):
        o, t, _ = _score(mod)
        ok += o; total += t
    assert ok / total >= 0.95, f"column reading fell to {ok}/{total}"


def test_personal_columns_are_never_missed():
    for mod in (mapping_cases, mapping_holdout, mapping_blind):
        _, _, misses = _score(mod)
        leaked = [m for m in misses if m[2] == "personal"]
        assert not leaked, f"personal columns not recognised: {leaked}"

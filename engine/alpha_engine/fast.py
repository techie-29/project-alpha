"""Speed helpers that give exactly the same answers as the plain pandas calls they replace.

Text columns repeat the same few values many times (store codes, statuses, cities). Trimming every cell one by one is
slow; trimming each distinct value once and spreading the result back is the same answer, many times faster.
Use as `s.alpha.strip_str()` for `s.astype(str).str.strip()` and `s.alpha.strip_string()` for
`s.astype("string").str.strip()`."""
from __future__ import annotations
import pandas as pd

_MIN = 2000          # small columns: the plain call is already fast


def _via_uniques(s: pd.Series, conv) -> pd.Series:
    if len(s) < _MIN or not (s.dtype == object or pd.api.types.is_string_dtype(s.dtype)
                             or isinstance(s.dtype, pd.CategoricalDtype)):
        return conv(s)
    codes, uniq = pd.factorize(s, use_na_sentinel=False)
    if len(uniq) > 0.5 * len(s):                         # mostly distinct values (ids): nothing to gain
        return conv(s)
    out = conv(pd.Series(uniq, dtype=object)).take(codes)
    out.index = s.index
    out.name = s.name
    return out


@pd.api.extensions.register_series_accessor("alpha")
class _Alpha:
    def __init__(self, s: pd.Series):
        self._s = s

    def strip_str(self) -> pd.Series:
        return _via_uniques(self._s, lambda x: x.astype(str).str.strip())

    def strip_string(self) -> pd.Series:
        return _via_uniques(self._s, lambda x: x.astype("string").str.strip())

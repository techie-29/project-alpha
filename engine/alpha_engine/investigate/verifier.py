"""Checks model wording before it reaches the owner. Every number in the text must have been produced by code (or be one of the
finding's own numbers); causal wording is refused. Anything that fails falls back to the plain template wording."""
from __future__ import annotations
import re

CAUSAL = re.compile(r"\b(caus(?:e|ed|es|ing)|because|due to|led to|leads? to|result(?:s|ed)? (?:of|from|in)|responsible for|thanks to|driven by|attributable)\b", re.I)
NUM = re.compile(r"(?<![\w.])([-+]?\d[\d,]*\.?\d*)\s*(%|[kKmMbB]\b)?")
MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"


def numbers_in(text: str) -> list[tuple[float, bool]]:
    """(value, strict). Strict numbers (with %, K/M suffix, decimals, or >= 32) must be backed; tiny plain integers and years are ignored."""
    out = []
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    t = re.sub(r"\b\d{1,2}\s+" + MONTHS + r"\s+\d{2,4}\b", " ", t, flags=re.I)
    for m in NUM.finditer(t):
        raw, suf = m.group(1).replace(",", ""), (m.group(2) or "")
        try:
            v = float(raw)
        except ValueError:
            continue
        if suf in ("k", "K"): v *= 1e3
        elif suf in ("m", "M"): v *= 1e6
        elif suf in ("b", "B"): v *= 1e9
        strict = bool(suf) or "." in raw or abs(v) >= 32
        if re.fullmatch(r"(19|20)\d\d", raw):
            strict = False
        out.append((v, strict))
    return out


def flatten(o, acc=None):
    acc = [] if acc is None else acc
    if isinstance(o, bool) or o is None:
        return acc
    if isinstance(o, (int, float)):
        acc.append(float(o))
    elif isinstance(o, dict):
        for k, v in o.items():
            flatten(v, acc); acc.extend(x for x, _ in numbers_in(str(k)))
    elif isinstance(o, (list, tuple)):
        for v in o:
            flatten(v, acc)
    elif isinstance(o, str):
        acc.extend(x for x, _ in numbers_in(o))
    return acc


def pool(*sources) -> list[float]:
    base = []
    for s in sources:
        flatten(s, base)
    ext = []
    for v in base:
        ext += [v, -v, v * 100, v / 100, v * 1000, v / 1000]
    return ext


def backed(v: float, allowed: list[float]) -> bool:
    for a in allowed:
        if a == 0:
            if abs(v) < 1e-9:
                return True
            continue
        if abs(v - a) <= 0.01 * abs(a) + 0.006:
            return True
        # allow rounding to 2-3 significant digits (e.g. 1.23M from 1,234,567)
        if abs(v - a) <= 0.0051 * abs(a):
            return True
    return False


def verify(text: str, *produced) -> tuple[bool, str]:
    if not isinstance(text, str) or not text.strip():
        return False, "empty"
    if len(text) > 900:
        return False, "too long"
    if CAUSAL.search(text):
        return False, "causal wording"
    allowed = pool(*produced)
    for v, strict in numbers_in(text):
        if strict and not backed(v, allowed):
            return False, f"number {v:g} was not produced by any calculation"
    return True, "ok"


# ------------------------------------------------------------------------------------------------ strict checking
# Used for AI-written findings and answers. A number in the text must come from the results the finding itself cites,
# written in one of the ways people write numbers: rounded to what is shown, as a percentage of a share (0.142 -> 14.2%),
# with K / M / B / lakh / crore, or as the change, difference or share between TWO numbers of the same cited result
# (14.0% -> 6.2% 'fell 7.8 points', 'down 56%'). Nothing else: no x1000 tricks, no numbers from other results.
NUM_STRICT = re.compile(r"(?<![\w.])([-+]?\d[\d,]*\.?\d*)-?\s*(%|percentage[- ]points?|points?|pts|pp|lakhs?|lacs?|crores?|cr\b|[kKmMbBL]\b)?", re.I)
SCALE = {"k": 1e3, "m": 1e6, "b": 1e9, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7}


def _numbers_strict(text: str) -> list[tuple[float, int, str]]:
    """(value, decimals shown, kind) with kind '%', 'pts' or ''. Years, dates and tiny counts are skipped as before."""
    out = []
    t = re.sub(r"\b\d{4}-\d{2}(-\d{2})?\b", " ", text)
    t = re.sub(r"\b\d{1,2}\s+" + MONTHS + r"\s+\d{2,4}\b", " ", t, flags=re.I)
    t = re.sub(MONTHS + r"\s+\d{4}\b", " ", t, flags=re.I)
    t = re.sub(r"\b(Q[1-4]|FY|H[12])\s?'?\d{2,4}\b", " ", t, flags=re.I)
    for m in NUM_STRICT.finditer(t):
        raw, suf = m.group(1).replace(",", "").rstrip("."), re.sub(r"[-\s]+", " ", (m.group(2) or "").lower()).strip()
        try:
            v = float(raw)
        except ValueError:
            continue
        if re.fullmatch(r"(19|20)\d\d", raw) and not suf:
            continue
        dec = len(raw.split(".")[1]) if "." in raw else 0
        kind = "%" if suf == "%" else ("pts" if suf in ("percentage points", "percentage point", "points", "point", "pts", "pp") else "")
        if suf in SCALE:
            v *= SCALE[suf]
            dec = -1                                                  # 1.2M: shown to 2 significant digits
        if not suf and "." not in raw and abs(v) < 32:
            continue                                                  # small whole numbers ('3 products', 'top 10') are not checked
        out.append((v, dec, kind))
    return out


COUNT_KEYS = {"rows_used", "groups", "rows", "total", "count", "n"}


def _nums(o, acc, values_only: bool = False):
    """values_only: leave out row counts (rows_used, rows per group...) - they may be quoted, but changes and shares
    between counts are not findings and would let almost any percentage near 100% pass."""
    if isinstance(o, bool) or o is None:
        return acc
    if isinstance(o, (int, float)):
        if o == o and abs(o) != float("inf"):
            acc.append(float(o))
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in ("evidence", "formula", "question", "why"):
                continue                                          # sample source rows and wording are not results
            if values_only and k in COUNT_KEYS and isinstance(v, (int, float)):
                continue
            _nums(v, acc, values_only)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _nums(v, acc, values_only)
    elif isinstance(o, str):
        acc.extend(x for x, _, _ in _numbers_strict(o))
    return acc


def _close(v: float, a: float, dec: int) -> bool:
    if dec < 0:                                                       # written with a suffix: 2-3 significant digits
        return abs(v - a) <= 0.051 * abs(a) + 1e-9
    half = 0.5 * 10 ** (-dec) + 1e-9                                  # what rounding to the shown decimals allows
    return abs(v - a) <= max(half, 0.0005 * abs(a))


def _matches(v: float, dec: int, kind: str, base: list[float]) -> bool:
    for a in base:
        if kind in ("%", "pts"):
            if abs(a) <= 1.5 and _close(v, a * 100, dec):               # a share written as a percent
                return True
            if _close(v, a, dec):                                     # already in percent
                return True
        elif _close(v, a, dec) or _close(-v, a, dec):
            return True
    return False


def _derived(v: float, dec: int, kind: str, base: list[float]) -> bool:
    """Change, difference or share between two numbers of one cited result."""
    xs = sorted(set(round(x, 9) for x in base))[:120]
    for i, a in enumerate(xs):
        for b in xs:
            if a == b:
                continue
            cands = []
            if b:
                cands += [(a / b - 1) * 100, (a / b) * 100]               # % change, share as %
                if kind == "":
                    cands.append(a / b)                                   # '2.3x'
            if kind == "pts" or (kind == "%" and abs(a) <= 1.5 and abs(b) <= 1.5):
                cands.append((a - b) * 100)                               # difference of two shares, in points
            if kind == "":
                cands.append(a - b)
                if abs(a + b) >= 100:
                    cands.append(a + b)                                   # 'together they lose 28,700'
            if kind in ("%", "pts"):
                cands += [(a - b)] if abs(a) > 1.5 else []
            for c in cands:
                if _close(abs(v), abs(c), dec):
                    return True
    return False


def verify_strict(text: str, cited: list, extra: list | None = None) -> tuple[bool, str]:
    """cited: the results this text says it rests on (each a dict/list of numbers). extra: shared context everyone may
    quote (the headline numbers). Returns (ok, reason)."""
    if not isinstance(text, str) or not text.strip():
        return False, "empty"
    if len(text) > 900:
        return False, "too long"
    if CAUSAL.search(text):
        return False, "causal wording (say 'lines up with', not 'because')"
    groups = [_nums(c, []) for c in (cited or [])]
    values = [_nums(c, [], True) for c in (cited or [])]
    common = _nums(extra or [], [])
    every = [x for g in groups for x in g] + common
    for v, dec, kind in _numbers_strict(text):
        if _matches(v, dec, kind, every):
            continue
        if any(_derived(v, dec, kind, g) for g in values if len(g) <= 160):
            continue
        shown = f"{v:g}{'%' if kind == '%' else (' points' if kind == 'pts' else '')}"
        return False, f"{shown} does not come from the results it cites"
    return True, "ok"

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

"""The finding card: one format for every insight the owner reads, whichever brain produced it (metric + AI, or full AI).

A card is only shown if it passes the gates below. They exist so that vague or weak output cannot reach the page:
  1. numbers   - every number in the text comes from the results the card cites (strict checker);
  2. specific  - the headline itself carries a number;
  3. compared  - it compares something (two groups, two periods, against the overall figure) - a lone total is not a finding;
  4. money     - it says how much money is involved (data-quality cards may say how many rows instead);
  5. evidence  - it cites results that came from real rows (rows used > 0), and the owner can open them or the code behind them;
  6. no cause  - no causal wording; and not a near-copy of another card.
Gates are checks on the form of the card, not on what it is about: they never decide which topics count."""
from __future__ import annotations
import re
from difflib import SequenceMatcher
from .investigate.verifier import verify_strict, _numbers_strict

TONES = ("risk", "strength", "data", "neutral")
CHART_TYPES = ("bar", "line", "table", "none")
COMPARE_WORDS = re.compile(r"\b(vs\.?|versus|than|compared|against|from .{1,40} to|while|whereas|but|only|of all|share|up|down|rose|fell|grew|dropped|higher|lower|"
                           r"more|less|above|below|half|double|twice|times|x the|gap|ahead|behind|biggest|smallest|largest|top|bottom|most|least)\b", re.I)


def _texts(card: dict) -> list[str]:
    out = [card.get("headline") or ""]
    out += [p for p in (card.get("points") or []) if isinstance(p, str)]
    for k in ("why_it_matters", "look_into"):
        if isinstance(card.get(k), str):
            out.append(card[k])
    m = card.get("money") or {}
    if isinstance(m.get("what"), str):
        out.append(m["what"])
    return [t for t in out if t]


def normalise(raw: dict, i: int, source: str) -> dict:
    """Take what a model wrote and keep only the fields of the card format, with safe types."""
    s = lambda x, n=400: (str(x).strip()[:n] if isinstance(x, (str, int, float)) else "")
    pts = [s(p, 300) for p in (raw.get("points") or []) if s(p, 300)][:5]
    money = raw.get("money") if isinstance(raw.get("money"), dict) else {}
    ch = raw.get("chart") if isinstance(raw.get("chart"), dict) else {}
    tone = raw.get("tone") if raw.get("tone") in TONES else "neutral"
    ev = [str(e) for e in (raw.get("evidence") or []) if isinstance(e, (str, int))][:6]
    return {"id": f"{source}-{i + 1}", "headline": s(raw.get("headline") or raw.get("title"), 200), "points": pts,
            "why_it_matters": s(raw.get("why_it_matters"), 300), "look_into": s(raw.get("look_into"), 300),
            "money": {"amount": money.get("amount") if isinstance(money.get("amount"), (int, float)) else None, "what": s(money.get("what"), 160)},
            "chart": {"type": ch.get("type") if ch.get("type") in CHART_TYPES else "none", "evidence": s(ch.get("evidence") or ch.get("request"), 40)},
            "tone": tone, "area": s(raw.get("area"), 30) or "general", "evidence": ev,
            "importance": raw.get("importance") if raw.get("importance") in ("high", "medium", "low") else "medium",
            "strength": raw.get("strength") if raw.get("strength") in ("Calculated", "Supported by evidence", "Possible") else "Calculated",
            "source": source}


def gate(card: dict, results: dict, headline_numbers: list | None = None, need_rows: bool = True, seen: list | None = None) -> tuple[bool, list[str]]:
    """results: {evidence id: {"ok": bool, "result": {...}, "rows_used": int, ...}}. Returns (ok, reasons it failed)."""
    why = []
    cited = [results[e] for e in card.get("evidence", []) if e in results and results[e].get("ok")]
    if not cited:
        return False, ["cites no successful result"]
    data_card = card.get("tone") == "data"
    nums = [r.get("result") for r in cited]
    for t in _texts(card):
        ok, reason = verify_strict(t, nums, headline_numbers)
        if not ok:
            why.append(f"'{t[:60]}': {reason}")
    if not _numbers_strict(card.get("headline") or "") and not re.search(r"\d", card.get("headline") or ""):
        why.append("the headline has no number")
    all_text = " ".join(_texts(card))
    multi = any(isinstance((r.get("result") or {}).get("rows"), list) and len((r.get("result") or {}).get("rows")) >= 2 for r in cited)
    if not (COMPARE_WORDS.search(all_text) and (multi or len(_numbers_strict(all_text)) >= 2)):
        why.append("compares nothing (needs two groups, two periods, or a figure against the whole)")
    amount = (card.get("money") or {}).get("amount")
    if not data_card:
        if amount is None:
            why.append("does not say how much money is involved")
        else:
            ok, reason = verify_strict(f"{float(amount):.2f}", nums, headline_numbers)
            if not ok and not verify_strict(f"{float(amount):.0f}", nums, headline_numbers)[0]:
                why.append(f"money amount {amount}: {reason}")
    if need_rows and not any(int(r.get("rows_used") or 0) > 0 for r in cited):
        why.append("no rows behind it")
    for other in seen or []:
        if SequenceMatcher(None, (other.get("headline") or "").lower(), (card.get("headline") or "").lower()).ratio() >= 0.8 or \
                (set(other.get("evidence") or []) == set(card.get("evidence") or []) and other.get("evidence")):
            why.append(f"repeats '{other.get('headline', '')[:50]}'")
            break
    return (not why), why


def gate_all(raw_cards: list, results: dict, source: str, headline_numbers: list | None = None, need_rows: bool = True, limit: int = 10) -> tuple[list, list]:
    kept, dropped = [], []
    order = {"high": 0, "medium": 1, "low": 2}
    cards = [normalise(c, i, source) for i, c in enumerate(raw_cards or []) if isinstance(c, dict)]
    cards.sort(key=lambda c: (order[c["importance"]], -(abs(c["money"]["amount"]) if c["money"]["amount"] is not None else 0)))
    for c in cards:
        ok, why = gate(c, results, headline_numbers, need_rows, kept)
        if ok and len(kept) < limit:
            kept.append(c)
        else:
            dropped.append({"headline": c["headline"], "why": why or ["over the limit of cards shown"]})
    return kept, dropped

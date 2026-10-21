"""From raw findings to what the owner reads: ranking, stories, suggestions, Fix/Keep/Watch/Plan, coverage, briefing.
All template wording; the AI step may later rewrite wording but never numbers."""
from __future__ import annotations
import numpy as np
from ..analyses.common import fmt_value
from ..model.concepts import CONCEPTS

STRENGTH_W = {"supported": 1.0, "calculated": 0.8, "early": 0.35}
TYPE_W = {"stockout": 1.0, "loss_makers": 1.0, "quiet_customers": 0.95, "group_difference": 0.9, "combination": 0.95, "change": 0.85, "trend": 0.85,
          "dead_stock": 0.85, "low_cover": 0.85, "relationship": 0.8, "share_shift": 0.75, "dependency": 0.8, "concentration": 0.6, "seasonality": 0.7,
          "weekday": 0.55, "new_customers": 0.7, "overstock": 0.7, "repeat": 0.45, "extreme_values": 0.5, "duplicates": 0.7}


def pattern_key(i: dict) -> str:
    la = i.get("look_at") or {}
    return f"{i['type']}|{i.get('metric') or ''}|{la.get('col') or ''}"


def score(i: dict, revenue_total: float | None) -> float:
    share = i.get("impact_share")
    if share is None and i.get("impact") and revenue_total:
        share = abs(i["impact"]) / revenue_total
        i["impact_share"] = float(share)
    money = min(1.0, np.sqrt(abs(share))) if share else 0.0
    s = (0.40 * money + 0.25 * STRENGTH_W.get(i["strength"], 0.5) + 0.15 * (1.0 if i.get("actionable") else 0.0)
         + 0.10 * {"bad": 1.0, "good": 0.6, "neutral": 0.3}[i["polarity"]] + 0.10) * TYPE_W.get(i["type"], 0.6)
    return round(float(s), 4)


def suggestion(i: dict) -> str | None:
    if i.get("suggestion"):
        return i["suggestion"]
    la, t, n = i.get("look_at") or {}, i["type"], i.get("numbers") or {}
    v, col = la.get("value"), (la.get("col") or "").replace("_", " ")
    ml = (i.get("metric_label") or "this measure").lower()
    if t == "group_difference":
        if i["polarity"] == "bad":
            if i.get("metric") == "margin":
                return f"Review prices, discounts and costs for {v} ({col}); its margin is well below the rest."
            return f"Find out why {ml} is worse for {v} ({col}). Open the rows behind it and look for a shared reason (product, supplier, process, staff)."
        if i["polarity"] == "good":
            return f"Learn from {v} ({col}): what it does differently may work elsewhere."
        return f"Keep an eye on {v} ({col}); it behaves differently from the rest."
    if t == "combination":
        return f"Look at {la.get('value')} together with {la.get('value2')}: the problem shows up in this combination, not in either one alone."
    if t in ("trend", "change"):
        if i["polarity"] == "bad":
            return "Check what changed in this period (prices, stock, staff, competitors, campaigns) and which groups drive it; related findings can point the way."
        if i["polarity"] == "good":
            return "Find out what is working here so it can be kept up."
        return None
    if t == "share_shift":
        up = (n.get("end") or 0) > (n.get("start") or 0)
        return f"Put more effort and stock behind {v}, which is growing." if up else f"Find out why {v} is losing share; decide whether to fix it or let it go."
    if t == "seasonality":
        return f"Plan stock, staff and promotions ahead of {n.get('peak_month')}; use the quieter {n.get('low_month')} for offers or maintenance."
    if t == "weekday":
        return f"Match staffing and promotions to the weekly rhythm: busiest {n.get('busiest')}, quietest {n.get('quietest')}."
    if t == "relationship" and i["polarity"] == "bad":
        return "Work on the driver side of this relationship; the outcome tends to follow it."
    if t == "concentration":
        return "Look after your biggest customers (service, loyalty) and widen the base so you depend less on a few."
    if t == "dependency":
        return "Make sure this relationship is secure, and work on reducing dependence on a single source of revenue."
    if t == "new_customers" and i["polarity"] == "bad":
        return "Review how new customers find you (marketing channels, campaigns) against a year ago."
    return None


def bucket(i: dict) -> str:
    if i["strength"] == "early":
        return "watch"
    if i["type"] in ("seasonality", "weekday", "share_shift", "concentration", "repeat") and i["polarity"] != "bad":
        return "plan"
    if i["polarity"] == "bad":
        return "fix"
    if i["polarity"] == "good":
        return "keep"
    return "watch"


def stories(items: list[dict]) -> list[dict]:
    """Group findings about the same thing (same group value, or a combination and its parts)."""
    keyset = lambda i: {(i["look_at"]["col"], i["look_at"]["value"])} | ({(i["look_at"].get("col2"), i["look_at"].get("value2"))} if i["look_at"].get("col2") else set()) \
        if i.get("look_at") and i["look_at"].get("value") else set()
    groups: list[list[dict]] = []
    for i in items:
        ks = keyset(i)
        home = None
        for g in groups:
            if ks and any(ks & keyset(j) for j in g):
                home = g; break
        (home.append(i) if home is not None else groups.append([i]))
    out = []
    for g in groups:
        lead = max(g, key=lambda x: x["score"])
        for j in g:
            j["story"] = lead["id"]
        out.append({"id": lead["id"], "title": lead["title"], "members": [j["id"] for j in g], "size": len(g), "score": lead["score"]})
    return sorted(out, key=lambda s: -s["score"])


def assemble(items: list[dict], tiles: list[dict], prefs: dict | None = None) -> dict:
    prefs = prefs or {}
    rev = next((t["value"] for t in tiles if t["metric"] == "revenue"), None)
    seen = set()
    uniq = []
    for i in items:
        if i["id"] in seen:
            continue
        seen.add(i["id"]); uniq.append(i)
    for i in uniq:
        i["pattern"] = pattern_key(i)
        i["owner_pref"] = prefs.get(i["pattern"])
        i["muted"] = i["owner_pref"] == "not_useful"
        i["score"] = score(i, rev) + (0.15 if i["owner_pref"] == "useful" else 0.0) - (1.0 if i["muted"] else 0.0)
        i["suggestion"] = suggestion(i)
        i["bucket"] = bucket(i)
    uniq.sort(key=lambda i: -i["score"])
    st = stories([i for i in uniq if not i["muted"]])
    lead_ids = {s["id"] for s in st}
    sugg = {"fix": [], "keep": [], "watch": [], "plan": []}
    for i in uniq:
        if i["muted"] or not i["suggestion"] or i["id"] not in lead_ids:
            continue
        sugg[i["bucket"]].append({"insight_id": i["id"], "title": i["title"], "action": i["suggestion"], "claim": i["claim"],
                                  "impact": i.get("impact"), "impact_unit": i.get("impact_unit"), "polarity": i["polarity"]})
    for k in sugg:
        sugg[k] = sugg[k][:10]
    return {"items": uniq, "stories": st, "suggestions": sugg}


def coverage(frames: dict, models: dict, insights: list[dict], overview: dict) -> list[dict]:
    """For every column: what Alpha did with it."""
    chart_cols, chart_metrics = set(), set()
    for s in overview.get("sections", []):
        for c in s["charts"]:
            if c.get("group_col"):
                chart_cols.add((c.get("source"), c["group_col"]))
            if c.get("metric"):
                chart_metrics.add((c.get("source"), c["metric"]))
    tagged = {}
    for i in insights:
        for t in i.get("tags", []):
            tagged.setdefault((i.get("source"), t), []).append(i["id"])
    out = []
    for name, fm in models.items():
        F = frames.get(name)
        for col, v in fm.get("columns", {}).items():
            con = CONCEPTS[v["concept"]]
            canon = next((k for k, c in (F.canon.items() if F else []) if c == col), None)
            uses = []
            if F and ((name, col) in chart_cols or (canon and any(m for (s, m) in chart_metrics if s == name and canon in m))):
                uses.append("charts")
            hits = tagged.get((name, col), []) + (tagged.get((name, canon), []) if canon else [])
            if hits:
                uses.append(f"{len(hits)} finding(s)")
            if con.kind == "date":
                status = "Used as the time axis" if F is not None and F.has_time else "Read as a date"
            elif v["concept"] in ("personal",):
                status = "Not analysed: personal detail (kept private)"
            elif v["concept"] == "free_text":
                status = "Not analysed: free text"
            elif con.kind == "key" and not uses:
                status = "Used to count and link records"
            elif uses:
                status = "Used in " + " and ".join(uses)
            elif con.kind in ("group", "number"):
                status = "Checked; nothing stood out"
            else:
                status = "Read, not used in this report"
            out.append({"file": name, "column": col, "concept": v["concept"], "label": v["label"], "confidence": v["confidence"], "status": status, "findings": hits[:5]})
    return out


def briefing(overview: dict, assembled: dict, warnings: list[str]) -> dict:
    items = [i for i in assembled["items"] if not i["muted"]]
    tiles = {t["metric"]: t for t in overview["tiles"]}
    key = []
    for mid in ("revenue", "orders", "customers", "profit", "margin", "stock_value"):
        t = tiles.get(mid)
        if not t:
            continue
        s = f"{t['label']} {fmt_value(t['value'], t['fmt'], t.get('unit') or '')}"
        if t.get("last_12_months") and t["last_12_months"].get("change") is not None:
            s += f" ({t['last_12_months']['change']:+.0%} last 12 months vs the 12 before)"
        elif t.get("vs_last_year") and t["vs_last_year"].get("change") is not None and t["fmt"] != "pct":
            s += f" ({t['vs_last_year']['change']:+.0%} on the same month last year)"
        key.append(s)
    leads = [i for i in items if i["id"] in {s["id"] for s in assembled["stories"]}]
    fix = [i for i in leads if i["bucket"] == "fix"]
    headline = (fix[0]["title"] + ".") if fix else (leads[0]["title"] + ".") if leads else "Nothing unusual stood out in what was checked."
    span = next((f for f in overview["files"] if f.get("from")), None)
    return {"headline": headline, "key_numbers": key,
            "coverage": (f"{sum((f['rows'] or 0) for f in overview['files']):,} rows across {len(overview['files'])} file(s)" + (f", {span['from']} to {span['to']}" if span else "")),
            "top": [{"insight_id": i["id"], "title": i["title"], "detail": i["detail"], "claim": i["claim"], "polarity": i["polarity"], "suggestion": i.get("suggestion")} for i in leads[:6]],
            "first_actions": [s for b in ("fix", "keep", "plan") for s in assembled["suggestions"][b]][:3],
            "caveats": warnings[:8], "how_to_read": "Each finding has a strength label. Calculated = arithmetic on your rows. Supported by evidence = passed shuffle tests that allow for chance. Possible (early sign) = worth watching. None of them claims a cause."}

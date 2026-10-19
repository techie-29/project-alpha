"""Whole-engine orchestration: read -> understand -> (AI review) -> link -> scan -> discover -> report."""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import pickle
import time
import datetime as dt
from pathlib import Path
import pandas as pd
from .llm import Provider, NullProvider
from .understand.reader import read_any
from .understand.prepare import prepare, Prepared
from .understand.ai_review import review_columns
from .link.linker import find_links, apply_link_confirmations, build_views
from .scan.engine import scan_view
from .scan.snapshot import snapshot
from .discover.discover import discover
from .report.build import your_data, evidence_sample, intelligence, briefing, questions, clean

_CACHE: dict = {}


def _file_conf(confirmations: dict, name: str) -> dict:
    c = {}
    for k, v in (confirmations.get("columns") or {}).items():
        f, _, col = k.partition("::")
        if f == name:
            c[col] = v
    if (confirmations.get("time_col") or {}).get(name):
        c["__time_col__"] = confirmations["time_col"][name]
    if (confirmations.get("rows_in_time_order") or {}).get(name):
        c["__rows_in_time_order__"] = True
    return c


def _load(spec: dict, confirmations: dict, provider: Provider) -> tuple[Prepared, list[str]]:
    path = Path(spec["path"])
    st = path.stat()
    fc = _file_conf(confirmations, spec["name"])
    key = (str(path), st.st_mtime_ns, st.st_size, json.dumps(fc, sort_keys=True), provider.name)
    if key in _CACHE:
        return _CACHE[key]
    df, rnotes = read_any(str(path))
    p = prepare(df, spec["name"], fc)
    p.notes = rnotes + p.notes
    status = review_columns(p.df, p.roles, provider) if p.kind != "summary" else {"status": "skipped"}
    p.ai_status = status  # type: ignore[attr-defined]
    if len(_CACHE) > 6:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (p, rnotes)
    return _CACHE[key]


def _columns_public(p: Prepared) -> list[dict]:
    out = []
    for c, i in p.roles.items():
        if c.startswith("__") or c == "_t":
            continue
        out.append({"name": c, "role": i["role"], "secondary": i.get("secondary", []), "confidence": i["confidence"], "reasons": i["reasons"][:3],
                    "needs_confirmation": bool(i.get("needs_confirmation")), "ai": i.get("ai"), "unique": i.get("unique"), "source": i.get("source", "auto")})
    return out


def read(files: list[dict], confirmations: dict | None = None, provider: Provider | None = None) -> dict:
    confirmations, provider = confirmations or {}, provider or NullProvider()
    tables = {}
    for spec in files:
        p, _ = _load(spec, confirmations, provider)
        tables[spec["name"]] = p
    links = apply_link_confirmations(find_links(tables), confirmations.get("links") or {})
    return clean({
        "files": [{"id": s.get("id"), "name": s["name"], "rows": int(len(tables[s["name"]].df)), "kind": tables[s["name"]].kind,
                   "time_col": tables[s["name"]].time_col, "columns": _columns_public(tables[s["name"]]),
                   "notes": tables[s["name"]].notes, "warnings": tables[s["name"]].warnings,
                   "ai": getattr(tables[s["name"]], "ai_status", None)} for s in files],
        "links": [l.public() for l in links],
    })


def analyze(analysis_id: str, files: list[dict], confirmations: dict | None, data_dir: str, provider: Provider | None = None,
            progress=lambda stage, pct: None, investigate=None) -> dict:
    t0 = time.time()
    confirmations, provider = confirmations or {}, provider or NullProvider()
    progress("Reading your files", 5)
    tables = {}
    for n, spec in enumerate(files):
        p, _ = _load(spec, confirmations, provider)
        tables[spec["name"]] = p
        progress(f"Understanding {spec['name']}", 5 + int(15 * (n + 1) / len(files)))
    reading = read(files, confirmations, provider)
    progress("Linking files", 25)
    links = apply_link_confirmations(find_links(tables), confirmations.get("links") or {})
    views, lnotes, lwarns = build_views(tables, links, {})
    progress("Looking for changes", 30)
    views_out, disc, snaps, state = [], [], [], []
    scannable = [v for v in views if v.kind in ("events", "periodic")]
    for n, v in enumerate(views):
        if v in scannable:
            sr = scan_view(v)
            if sr is None:
                v.warnings.append("Not enough usable dates (needs at least 12 periods) to look for changes over time.")
                continue
            d = discover(sr)
            for f in d["findings"][:30]:
                f["rows"] = evidence_sample(sr, f)
            views_out.append(your_data(v, sr)); disc.append(d); state.append((v, sr))
        elif v.kind in ("reference", "no_time", "dimension"):
            s = snapshot(v)
            if s:
                snaps.append(s)
        progress(f"Checked {v.name}", 30 + int(55 * (n + 1) / len(views)))
    progress("Writing the report", 90)
    findings = [f for d in disc for f in d["findings"]]
    findings.sort(key=lambda f: (0 if f["level"] == "confirmed" else 1, -(f["numbers"]["impact_share"] or 0), f["q"]))
    report = {
        "version": 1, "analysis_id": analysis_id, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files": [{"name": s["name"], "rows": int(len(tables[s["name"]].df)), "kind": tables[s["name"]].kind} for s in files],
        "reading": reading, "link_notes": lnotes, "link_warnings": lwarns,
        "briefing": briefing(files, views_out, disc, reading),
        "your_data": views_out,
        "insights": {"findings": findings, "stories": [s for d in disc for s in d["stories"]], "seasonal": [s for d in disc for s in d["seasonal"]],
                     "snapshots": snaps, "quiet": not findings,
                     "checked": {"series": sum(d["checked"]["series"] for d in disc), "tests": sum(d["checked"]["tests"] for d in disc),
                                 "dropped_duplicate_measures": [x for d in disc for x in d["dropped_duplicates"]][:30]}},
        "intelligence": intelligence(findings),
        "questions": questions(findings),
        "not_explained": [{"finding_id": f["id"], "title": f["title"], "share": f["drivers"]["not_explained"]} for f in findings if f.get("drivers") and f["drivers"]["not_explained"] > 0.3][:10],
        "limits": ["Amounts in different currencies are never added together.", "Findings describe what changed and what it lines up with; they do not prove a cause.",
                   "Statistical minimums used: 30 rows per group, 3 rows per period, 4 periods per side, 5 rows per period to confirm."],
        "ai": {"provider": provider.name, "investigation": None},
        "seconds": round(time.time() - t0, 1),
    }
    if investigate is not None:
        progress("Investigating the strongest leads", 93)
        report = investigate(report, state)
    report = clean(report)
    out = Path(data_dir) / "analyses" / analysis_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report), encoding="utf-8")
    save_state(out / "state.pkl.gz", state)
    progress("Done", 100)
    return report


def save_state(path: Path, state: list) -> None:
    """Slim copies of each view, so Ask Alpha can answer later without re-reading the uploads."""
    slim = []
    for v, sr in state:
        keep = [c for c in v.df.columns if not c.startswith("__rate__")]
        slim.append({"name": v.name, "time_col": v.time_col, "money_col": v.money_col, "currency_col": v.currency_col, "slices": v.slices,
                     "ok": v.ok.values, "roles": {c: {k: i[k] for k in ("role", "unique") if k in i} for c, i in v.roles.items()}, "df": v.df[keep].copy(), "step": sr.axis.step, "notes": v.notes})
    with gzip.open(path, "wb") as fh:
        pickle.dump(slim, fh, protocol=5)

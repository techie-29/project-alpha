"""Whole-engine orchestration (v5):
read -> understand columns -> business model -> link -> views -> frames -> overview -> analysis toolbox -> insights -> (AI) -> report."""
from __future__ import annotations
import datetime as dt
import gzip
import json
import pickle
import time
from pathlib import Path
from .llm import Provider, NullProvider
from .understand.reader import read_any
from .understand.prepare import prepare, Prepared
from .understand.ai_review import review_columns
from .link.linker import find_links, apply_link_confirmations, build_views
from .model.build import build_model
from .model.concepts import CONCEPTS
from .metrics.frame import build_frame
from .overview.build import build_overview, pick_frames
from .analyses.run import run_all
from .insights.assemble import assemble, coverage, briefing
from .report.build import clean

_CACHE: dict = {}
VERSION = 2


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


def _load(spec: dict, confirmations: dict, provider: Provider) -> Prepared:
    path = Path(spec["path"])
    st = path.stat()
    fc = _file_conf(confirmations, spec["name"])
    key = (str(path), st.st_mtime_ns, st.st_size, json.dumps(fc, sort_keys=True), provider.name)
    if key in _CACHE:
        return _CACHE[key]
    df, rnotes = read_any(str(path))
    p = prepare(df, spec["name"], fc)
    p.notes = rnotes + p.notes
    p.ai_status = review_columns(p.df, p.roles, provider) if p.kind != "summary" else {"status": "skipped"}   # type: ignore[attr-defined]
    if len(_CACHE) > 8:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = p
    return p


def _understand(files: list[dict], confirmations: dict, provider: Provider, memory: dict | None, progress=None):
    tables = {}
    for n, spec in enumerate(files):
        tables[spec["name"]] = _load(spec, confirmations, provider)
        if progress:
            progress(f"Reading {spec['name']}", 3 + int(17 * (n + 1) / len(files)))
    links = apply_link_confirmations(find_links(tables), confirmations.get("links") or {})
    model = build_model(tables, links, confirmations, memory)
    from .investigate.ai import review_concepts
    model["ai_review"] = review_concepts(model, tables, provider)
    for name, p in tables.items():                              # the AI review may have changed some meanings
        p.concepts = {c: v["concept"] for c, v in model["files"][name]["columns"].items()}
    return tables, links, model


def _reading(files, tables, links, model) -> dict:
    out = []
    for s in files:
        p, fm = tables[s["name"]], model["files"][s["name"]]
        cols = []
        for c, i in p.roles.items():
            if c.startswith("__") or c in ("_t", "_row"):
                continue
            v = fm["columns"].get(c, {})
            cols.append({"name": c, "type": i["role"], "type_confidence": i["confidence"], "concept": v.get("concept"), "label": v.get("label"),
                         "confidence": v.get("confidence"), "reasons": v.get("reasons", [])[:3], "alternatives": v.get("alternatives", [])[:3],
                         "needs_confirmation": bool(v.get("needs_confirmation")) or bool(i.get("needs_confirmation") and i["role"] not in ("empty", "constant")),
                         "source": v.get("source", "auto"), "unique": i.get("unique")})
        out.append({"id": s.get("id"), "name": s["name"], "rows": int(len(p.df)), "kind": p.kind, "role": fm["file"].get("role"), "entity": fm["file"].get("entity"),
                    "role_reason": fm["file"].get("reason"), "time_col": p.time_col, "columns": cols, "identities": [i["text"] for i in fm.get("identities", [])][:8],
                    "notes": p.notes, "warnings": p.warnings, "ai": getattr(p, "ai_status", None)})
    return {"files": out, "links": [l.public() for l in links], "entities": model["entities"], "ai_review": model.get("ai_review"),
            "concepts": [{"id": c.id, "label": c.label, "kind": c.kind, "area": c.area} for c in CONCEPTS.values()]}


def read(files: list[dict], confirmations: dict | None = None, provider: Provider | None = None, memory: dict | None = None) -> dict:
    confirmations, provider = confirmations or {}, provider or NullProvider()
    tables, links, model = _understand(files, confirmations, provider, memory)
    return clean(_reading(files, tables, links, model))


def analyze(analysis_id: str, files: list[dict], confirmations: dict | None, data_dir: str, provider: Provider | None = None,
            progress=lambda stage, pct: None, investigate=None, preferences: dict | None = None, memory: dict | None = None) -> dict:
    t0 = time.time()
    confirmations, provider = confirmations or {}, provider or NullProvider()
    progress("Reading your files", 2)
    tables, links, model = _understand(files, confirmations, provider, memory, progress)
    progress("Linking files into one business", 22)
    views, lnotes, lwarns = build_views(tables, links, {})
    frames = {}
    for v in views:
        if v.kind == "summary" or v.name not in model["files"]:
            continue
        fm = model["files"][v.name]
        frames[v.name] = build_frame(v, fm["columns"], fm["file"], tables, links, model["files"])
    progress("Building the overview", 28)
    overview = build_overview(frames, {n: m["file"] for n, m in model["files"].items()}, links)
    pick = pick_frames(frames, links)
    raw, checked = run_all(pick, {v.name: v for v in views}, progress)
    progress("Ranking what matters", 88)
    asm = assemble(raw, overview["tiles"], preferences)
    warnings = list(dict.fromkeys(lwarns + [w for p in tables.values() for w in p.warnings]))
    unsure = sum(1 for fm in model["files"].values() for v in fm["columns"].values() if v.get("needs_confirmation"))
    if unsure:
        warnings.insert(0, f"{unsure} column(s) were read with low confidence. Check them on the 'How I read your files' screen; findings that use them are less certain.")
    report = {
        "version": VERSION, "analysis_id": analysis_id, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files": [{"name": s["name"], "rows": int(len(tables[s["name"]].df)), "role": model["files"][s["name"]]["file"].get("role")} for s in files],
        "reading": _reading(files, tables, links, model), "link_notes": lnotes, "link_warnings": lwarns,
        "overview": overview,
        "insights": {"items": asm["items"], "stories": asm["stories"], "checked": checked, "quiet": not any(i["strength"] != "calculated" for i in asm["items"])},
        "suggestions": asm["suggestions"],
        "coverage": coverage(frames, model["files"], asm["items"], overview),
        "briefing": briefing(overview, asm, warnings),
        "questions": _questions(asm["items"]),
        "limits": ["Amounts in different currencies are never added together; the main currency is shown and others are listed.",
                   "Findings describe what the data shows and what lines up with what. They do not prove causes.",
                   "Statistical minimums: 30 rows per group, 40 rows per combination, 12 months for trends, 2 full years for seasonality."],
        "ai": {"provider": provider.name, "investigation": None},
    }
    if investigate is not None:
        progress("The AI helper is checking leads and asking its own questions", 92)
        try:
            report = investigate(report, frames)
        except Exception as e:
            report["ai"]["investigation"] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
    report["seconds"] = round(time.time() - t0, 1)
    report = clean(report)
    out = Path(data_dir) / "analyses" / analysis_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report), encoding="utf-8")
    save_state(out / "state.pkl.gz", frames, model)
    progress("Done", 100)
    return report


def _questions(items: list[dict]) -> list[dict]:
    out = []
    for i in items[:12]:
        if i["muted"] or i["type"] not in ("change", "trend", "group_difference", "combination") or i["polarity"] != "bad":
            continue
        when = f" around {i['when']}" if i.get("when") else ""
        la = i.get("look_at") or {}
        where = f" for {la['value']}" if la.get("value") else ""
        out.append({"id": i["id"], "insight_id": i["id"], "text": f"{i['title']}. Did anything happen{where}{when} that the files would not show (a price change, a supplier or staff change, a competitor, a closure)?"})
        if len(out) >= 5:
            break
    return out


def save_state(path: Path, frames: dict, model: dict) -> None:
    """The analysis frames (all files, business meanings attached), so Ask Alpha can answer later without re-reading uploads."""
    with gzip.open(path, "wb", compresslevel=1) as fh:
        pickle.dump({"version": 2, "frames": frames}, fh, protocol=5)


def load_state(path: Path) -> dict:
    with gzip.open(path, "rb") as fh:
        st = pickle.load(fh)
    return st.get("frames", {}) if isinstance(st, dict) else {}

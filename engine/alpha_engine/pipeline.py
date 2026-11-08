"""Whole-engine orchestration (v5):
read -> understand columns -> business model -> link -> views -> frames -> overview -> analysis toolbox -> insights -> (AI) -> report."""
from __future__ import annotations
import datetime as dt
import gzip
import json
import os
import pickle
import threading
import time
import pandas as pd
from pathlib import Path
from .llm import Provider, NullProvider
from .validate import validate
from . import clean as cleaning_stage
from .understand.reader import read_any, table_sheets
from .understand.dates import unpivot_periods, unpivot_tickers
from .understand.prepare import prepare, Prepared
from .understand.ai_review import review_columns
from .link.linker import find_links, apply_link_confirmations, build_views
from .model.build import build_model
from .model.concepts import CONCEPTS
from .metrics.frame import build_frame, relabel
from .overview.build import build_overview, pick_frames
from .analyses.run import run_all
from .insights.assemble import assemble, coverage, briefing
from .report.build import clean

_CACHE: dict = {}
_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()
VERSION = 2


def _file_conf(confirmations: dict, name: str) -> dict:
    c = {}
    for k, v in (confirmations.get("columns") or {}).items():
        f, _, col = k.partition("::")
        if f == name:
            c[col] = v
    if (confirmations.get("time_col") or {}).get(name):
        c["__time_col__"] = confirmations["time_col"][name]
    for col, order in ((confirmations.get("date_order") or {}).get(name) or {}).items():
        c[f"__date_order__::{col}"] = order
    if (confirmations.get("rows_in_time_order") or {}).get(name):
        c["__rows_in_time_order__"] = True
    # the owner's choices for cleaning and naming (all keyed by the column's ORIGINAL name; renamed columns are translated)
    fixes = (confirmations.get("fixes") or {})
    if fixes.get(name) or fixes.get("*"):
        c["__fix__"] = {**(fixes.get("*") or {}), **(fixes.get(name) or {})}
    hints = {}
    for src in (confirmations.get("mapped") or {}, confirmations.get("concepts") or {}):
        for k, v in src.items():
            f, _, col = k.partition("::")
            if f == name and isinstance(v, str):
                hints[col] = v
    if hints:
        c["__hints__"] = hints
    ren = {k.partition("::")[2]: v for k, v in (confirmations.get("rename") or {}).items() if k.partition("::")[0] == name and str(v).strip()}
    if ren:
        c["__rename__"] = ren
        for old, new in ren.items():                           # choices made on the original name still apply after renaming
            for key in [k for k in list(c) if not k.startswith("__")]:
                if key == old:
                    c[new] = c[key]
    return c


SHEET_SEP = " › "
MAX_SHEETS = 20


def expand_files(files: list[dict]) -> list[dict]:
    """A workbook with several table sheets becomes one table per sheet ('Book.xlsx › Orders'), so nothing in it is
    ignored; note / cover sheets are skipped. Single-table files are unchanged."""
    out = []
    for spec in files:
        if spec.get("sheet") is not None:
            out.append(spec); continue
        sheets = table_sheets(spec["path"])
        if len(sheets) <= 1:
            out.append(spec); continue
        for name, _ in sheets[:MAX_SHEETS]:
            out.append({**spec, "name": f"{spec['name']}{SHEET_SEP}{name}", "sheet": name, "workbook": spec["name"]})
    return out


def _load(spec: dict, confirmations: dict, provider: Provider) -> Prepared:
    path = Path(spec["path"])
    st = path.stat()
    fc = _file_conf(confirmations, spec["name"])
    # the AI's look at unclear columns is kept on the table itself (ai_status), so a table read once (right after upload,
    # or on the reading screen) is reused by the full analysis whichever AI setting asked for it
    key = (str(path), spec.get("sheet"), spec["name"], st.st_mtime_ns, st.st_size, json.dumps(fc, sort_keys=True))
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock:                       # read after upload still running: wait for it and reuse its work instead of reading twice
        if key in _CACHE:
            _CACHE[key] = _CACHE.pop(key)                   # most recently used last
            return _CACHE[key]
        return _read_table(spec, path, fc, key)


def _inherit_ai(p: Prepared, key: tuple) -> None:
    """The same file read again with different cleaning or naming choices must not pay for the AI's look at its columns a second
    time: take the answer from an earlier read of the same file (same columns, same roles) instead of asking again."""
    if p.ai_status is not None:
        return
    for k, old in reversed(list(_CACHE.items())):
        st = getattr(old, "ai_status", None)
        if k[:5] != key[:5] or not st or st.get("provider") in (None, "none") or st.get("status") != "ok" and not st.get("asked") == 0:
            continue
        if list(old.df.columns) != list(p.df.columns):
            continue
        for c, info in old.roles.items():
            if c in p.roles and info.get("ai") and p.roles[c].get("role") == info.get("role"):
                p.roles[c]["ai"] = info["ai"]
        p.ai_status = dict(st)
        return


def _read_table(spec: dict, path: Path, fc: dict, key: tuple) -> Prepared:
    df, rnotes = read_any(str(path), spec.get("sheet"))
    if spec.get("sheet") is not None:
        rnotes = [f"Sheet '{spec['sheet']}' of {spec.get('workbook') or path.name}."] + rnotes
    # cell-level cleaning (before anything is learned from the data): safe fixes on their own, the owner's choice for the rest
    cleaning = None
    try:
        df, cleaning = cleaning_stage.run(df, spec["name"], rnotes, fc.get("__hints__"), fc.get("__fix__"))
        if any(a["id"] == "duplicate_rows" for a in cleaning["auto"]):          # the reader kept a few copies; cleaning removed them
            rnotes = [x for x in rnotes if "are exact copies of other rows. They were kept" not in x]
        rnotes = rnotes + _cleaning_notes(cleaning)
    except Exception as e:                                   # cleaning must never stop a file from being read
        rnotes = rnotes + [f"Cell-level cleaning could not run on this table ({type(e).__name__})."]
    original = {}
    ren = {o: n for o, n in (fc.get("__rename__") or {}).items() if o in df.columns and n and n != o}
    if ren:
        taken = set(df.columns) - set(ren)
        final = {}
        for o, n in ren.items():
            n = str(n).strip()[:60]
            while n in taken or n in final.values():
                n += " (2)"
            final[o] = n
        df = df.rename(columns=final)
        original = {n: o for o, n in final.items()}
        rnotes = rnotes + [f"You renamed {len(final)} column(s): " + ", ".join(f"{o} → {n}" for o, n in list(final.items())[:6]) + "."]
    df, wide_note = unpivot_periods(df, spec["name"])
    if not wide_note:
        df, wide_note = unpivot_tickers(df)
    if wide_note:
        rnotes = rnotes + [wide_note]
    p = prepare(df, spec["name"], fc)
    p.cleaning = cleaning                                      # type: ignore[attr-defined]
    p.original_names = original                                # type: ignore[attr-defined]
    p.notes = rnotes + p.notes
    p.ai_status = None if p.kind != "summary" else {"status": "skipped"}   # type: ignore[attr-defined]  (asked in _understand)
    _inherit_ai(p, key)
    _CACHE[key] = p
    _trim_cache()
    if len(_LOCKS) > 400:
        _LOCKS.clear()
    return p


def _cleaning_notes(rep: dict) -> list[str]:
    """Plain-language lines about what cleaning did, so the data check and the report can show them."""
    out = []
    for g in rep["groups"]:
        pick = next((c["label"] for c in g["choices"] if c["id"] == g["choice"]), g["choice"])
        if g["choice"] in ("blank", "remove", "fill", "merge", "suggest"):
            out.append(f"{g['title']} ({g['count']}) in {', '.join(g['columns']) or 'the rows'}: {pick.lower()}.")
    return out


MAX_CACHED_ROWS = int(os.environ.get("ALPHA_CACHE_ROWS", "3000000"))


def _trim_cache() -> None:
    """Keep recently read tables in memory (up to ALPHA_CACHE_ROWS rows in all, default 3 million), so the reading screen
    and the analysis after it do not read the same workbook twice. The oldest are forgotten first."""
    while len(_CACHE) > 1 and (len(_CACHE) > 80 or sum(len(p.df) for p in _CACHE.values()) > MAX_CACHED_ROWS):
        _CACHE.pop(next(iter(_CACHE)))


def warm(files: list[dict]) -> int:
    """Read and prepare uploaded files straight away (no AI, nothing saved), so the reading screen opens quickly.
    Returns the number of tables prepared; a file that cannot be read is skipped (the reading screen will say why)."""
    n = 0
    for spec in expand_files(files):
        try:
            _load(spec, {}, NullProvider()); n += 1
        except Exception:
            continue
    return n


def _review_all(tables: dict, provider: Provider, progress=None) -> None:
    """The AI's look at unclear columns: one question per table, all asked at the same time instead of one after another
    (each answer only touches its own table)."""
    def asked(p) -> bool:
        st = getattr(p, "ai_status", None)
        return st is not None and (provider.name == "none" or st.get("provider") == provider.name or st.get("status") in ("nothing to ask", "skipped"))
    todo = [p for p in tables.values() if not asked(p)]
    if not todo:
        return
    if provider.name == "none" or len(todo) == 1:
        for p in todo:
            p.ai_status = {**review_columns(p.df, p.roles, provider), "provider": provider.name}
        return
    if progress:
        progress("Asking the AI about unclear columns", 20)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(6, len(todo)), thread_name_prefix="alpha-review") as ex:
        for p, st in zip(todo, ex.map(lambda p: review_columns(p.df, p.roles, provider), todo)):
            p.ai_status = {**st, "provider": provider.name}


def _understand(files: list[dict], confirmations: dict, provider: Provider, memory: dict | None, progress=None):
    tables = {}
    for n, spec in enumerate(files):
        tables[spec["name"]] = _load(spec, confirmations, provider)
        if progress:
            progress(f"Reading {spec['name']}", 3 + int(17 * (n + 1) / len(files)))
    _review_all(tables, provider, progress)
    links = apply_link_confirmations(find_links(tables), confirmations.get("links") or {})
    model = build_model(tables, links, confirmations, memory)
    _settle_masters(tables, model)
    _share_currency(model)
    from .investigate.ai import review_concepts
    model["ai_review"] = review_concepts(model, tables, provider)
    for name, p in tables.items():                              # the AI review may have changed some meanings
        p.concepts = {c: v["concept"] for c, v in model["files"][name]["columns"].items()}
    return tables, links, model


def _settle_masters(tables: dict, model: dict) -> None:
    """A list of products, stores, suppliers or staff keeps its dates (launched, opened, joined) as details of each record;
    they are not when things happened, so the list is used as detail for the tables that link to it."""
    for name, fm in model["files"].items():
        P = tables.get(name)
        if P is not None and fm["file"].get("dated_master") and P.time_col:
            P.notes.append(f"'{P.time_col}' describes each {fm['file'].get('entity') or 'record'} (it is not when something happened), so this table is a list, not a log.")
            P.time_col = None
            if P.kind not in ("summary",):
                P.kind = "reference"


def _share_currency(model: dict) -> None:
    """One business, one currency: when some tables state their currency (spend_inr, amount_inr) and exactly one currency is
    found, tables that do not say are in the same currency. Two or more currencies are left alone (never mixed)."""
    found = {v.get("constant") for fm in model["files"].values() for v in fm["columns"].values() if v.get("concept") == "currency" and v.get("constant")}
    if len(found) != 1:
        return
    code = next(iter(found))
    for fm in model["files"].values():
        if not any(v.get("concept") == "currency" for v in fm["columns"].values()) and any(
                CONCEPTS[v["concept"]].money for v in fm["columns"].values() if v.get("concept") in CONCEPTS):
            fm["columns"]["__currency__"] = {"concept": "currency", "label": "Currency", "confidence": 0.7, "source": "auto", "constant": code, "alternatives": [],
                                             "reasons": [f"other tables in this upload are in {code}"]}


PROFILE_HIDE = {"personal", "birth_date"}


def _profile(s, role: str, hide: bool) -> dict:
    """A quick look at one column for the data dictionary: how full it is, how varied, a few examples and its spread or top values."""
    n = len(s)
    filled = s.notna() & (s.astype(str).str.strip() != "")
    vals = s[filled]
    out = {"filled": round(float(filled.mean()), 4) if n else 0.0, "blank": int(n - filled.sum()), "unique": int(vals.nunique())}
    if hide:
        out["hidden"] = True
        return out
    if pd.api.types.is_datetime64_any_dtype(vals):
        midnight = bool((vals.dt.normalize() == vals).all())
        vals = vals.dt.strftime("%Y-%m-%d" if midnight else "%Y-%m-%d %H:%M")
        out["first"], out["last"] = (str(vals.min()), str(vals.max())) if len(vals) else (None, None)
    out["examples"] = [str(v)[:40] for v in vals.drop_duplicates().head(3)]
    num = pd.to_numeric(vals, errors="coerce") if role == "measure" else None
    if num is not None and num.notna().mean() > 0.9:
        num = num.dropna()
        out["stats"] = {"min": float(num.min()), "max": float(num.max()), "mean": float(num.mean()), "median": float(num.median())}
    elif role not in ("time",) and out["unique"]:
        top = vals.astype(str).value_counts().head(5)
        if top.iloc[0] > 1:                     # an id column (every value once) has no "top values"
            out["top"] = [{"value": str(k)[:40], "count": int(v)} for k, v in top.items()]
    return out


def _column_issues(p) -> dict:
    """What cleaning found per column, in plain words."""
    rep = getattr(p, "cleaning", None) or {}
    out: dict = {}
    for a in rep.get("auto", []):
        col = a.get("id", "").split(":", 1)[-1] if ":" in a.get("id", "") else None
        if col:
            out.setdefault(col, []).append(a.get("what", "fixed automatically"))
    for g in rep.get("groups", []):
        for col in g.get("columns", []):
            share = "" if len(g.get("columns", [])) == 1 else " (shared with other columns)"
            out.setdefault(col, []).append(f"{g.get('title', 'Problem')}: {g.get('count', 0):,} cell(s){share}")
    return out


def _reading(files, tables, links, model) -> dict:
    out = []
    for s in files:
        p, fm = tables[s["name"]], model["files"][s["name"]]
        issues = _column_issues(p)
        cols = []
        for c, i in p.roles.items():
            if c.startswith("__") or c in ("_t", "_row"):
                continue
            v = fm["columns"].get(c, {})
            cols.append({"name": c, "original": (getattr(p, "original_names", {}) or {}).get(c, c), "type": i["role"], "type_confidence": i["confidence"], "concept": v.get("concept"), "label": v.get("label"),
                         "confidence": v.get("confidence"), "reasons": v.get("reasons", [])[:3], "alternatives": v.get("alternatives", [])[:3],
                         # a column whose meaning is clear does not need its type checked (an id read as an id, a rating as a number)
                         "needs_confirmation": bool(v.get("needs_confirmation")) or bool(i.get("needs_confirmation") and i["role"] not in ("empty", "constant")
                                                                                          and (v.get("confidence") or 0) < 0.7
                                                                                          and v.get("concept") not in ("entity_id", "number", "group", "personal", "free_text", None)),
                         "unsure_between": v.get("unsure_between"),
                         "source": v.get("source", "auto"), "unique": i.get("unique"),
                         "profile": _profile(p.df[c], i["role"], v.get("concept") in PROFILE_HIDE) if c in p.df.columns else None,
                         "issues": issues.get((getattr(p, "original_names", {}) or {}).get(c, c), []) or issues.get(c, [])})
            if i["role"] == "time":
                cols[-1]["date"] = {"order": i.get("date_order"), "certain": bool(i.get("date_certain", True)), "example": i.get("date_example"),
                                    "reason": i.get("date_reason"), "from": i.get("date_min"), "to": i.get("date_max"), "grain": i.get("date_grain"),
                                    "styles": i.get("date_shapes"), "by_owner": i.get("date_source") == "owner"}
        dcols = [c for c, i in p.roles.items() if i["role"] == "time" and not c.startswith("__")]
        out.append({"id": s.get("id"), "name": s["name"], "rows": int(len(p.df)), "kind": p.kind, "role": fm["file"].get("role"), "entity": fm["file"].get("entity"),
                    "date_columns": dcols,
                    "role_reason": fm["file"].get("reason"), "time_col": p.time_col, "columns": cols, "identities": [i["text"] for i in fm.get("identities", [])][:8],
                    "notes": p.notes, "warnings": p.warnings, "ai": getattr(p, "ai_status", None)})
    return {"files": out, "links": [l.public() for l in links], "entities": model["entities"], "ai_review": model.get("ai_review"),
            "concepts": [{"id": c.id, "label": c.label, "kind": c.kind, "area": c.area} for c in CONCEPTS.values()]}


def quality(files: list[dict], confirmations: dict | None = None, memory: dict | None = None) -> dict:
    """The data-quality screen: for every table, what cleaning found (cell by cell), what it fixed by itself, and what the owner can decide.
    The answer reflects the choices already in `confirmations`, so it can be asked again after each change."""
    confirmations = confirmations or {}
    out, totals = [], {"issues": 0, "auto": 0, "decisions": 0, "cells": 0, "rows_before": 0, "rows_after": 0, "removed": 0}
    for spec in expand_files(files):
        p = _load(spec, confirmations, NullProvider())
        rep = getattr(p, "cleaning", None)
        if not rep:
            out.append({"file": spec["name"], "error": "This table could not be checked."}); continue
        out.append(rep)
        for k in ("issues", "auto", "decisions", "rows_before", "rows_after", "removed"):
            totals[k] += rep["summary"][k]
        totals["cells"] += rep["cells"]
    from .clean.scan import health
    totals["health"] = health(totals["issues"], totals["cells"])
    return clean_json({"files": out, "totals": totals})


def clean_json(o):
    return clean(o)


def read(files: list[dict], confirmations: dict | None = None, provider: Provider | None = None, memory: dict | None = None) -> dict:
    confirmations, provider = confirmations or {}, provider or NullProvider()
    files = expand_files(files)
    tables, links, model = _understand(files, confirmations, provider, memory)
    return clean(_reading(files, tables, links, model))


def analyze(analysis_id: str, files: list[dict], confirmations: dict | None, data_dir: str, provider: Provider | None = None,
            progress=lambda stage, pct: None, investigate=None, preferences: dict | None = None, memory: dict | None = None) -> dict:
    t0 = time.time()
    confirmations, provider = confirmations or {}, provider or NullProvider()
    progress("Reading your files", 2)
    files = expand_files(files)
    tables, links, model = _understand(files, confirmations, provider, memory, progress)
    progress("Linking files into one business", 22)
    views, lnotes, lwarns = build_views(tables, links, {})
    frames = {}
    for v in views:
        if v.kind == "summary" or v.name not in model["files"]:
            continue
        fm = model["files"][v.name]
        frames[v.name] = build_frame(v, fm["columns"], fm["file"], tables, links, model["files"])
    progress("Checking your data", 26)
    try:
        data_check = validate(tables, frames, model, links)
    except Exception as e:                                   # a failing check must never stop the report
        data_check = {"headline": "The data checks could not run.", "error": f"{type(e).__name__}: {str(e)[:160]}", "files": [], "rows": {}, "rows_in": 0}
    progress("Building the overview", 28)
    infos = {n: m["file"] for n, m in model["files"].items()}
    views_by = {v.name: v for v in views}
    parts, raw, checked = [], [], {"timing": {}, "parts": []}
    for k, names in enumerate(_clusters(frames, links)):
        sub = {n: frames[n] for n in names}
        ov = build_overview(sub, {n: infos[n] for n in names}, links)
        label = _part_label(sub, ov)
        rev = next((t["value"] for t in ov["tiles"] if t["metric"] == "revenue"), None)
        activity = [F for F in sub.values() if F.role in ("transactions", "periodic", "lines")] or [None]
        pk0 = pick_frames(sub, links)
        main_names = {pk0["sales"].name if pk0["sales"] else None, pk0["lines"].name if pk0["lines"] else None}
        runs = [pk0] + [{**pk0, "sales": F, "lines": None, "stock": None} for F in activity if F is not None and F.name not in main_names and F.role != "lines"]
        part_items = []
        for j, pk in enumerate(runs):
            if not (pk.get("sales") or pk.get("stock") or pk.get("lines")):
                continue
            items, ch = run_all(pk, views_by, lambda s, pc: progress(f"{label}: {s}", min(86, 30 + int((pc - 30) * (k + 1) / max(1, len(frames))))))
            part_items += items
            for kk, vv in ch.get("timing", {}).items():
                checked["timing"][kk] = round(checked["timing"].get(kk, 0) + vv, 1)
            if ch.get("failed"):
                checked.setdefault("failed", []).extend(ch["failed"])
        nouns = (pk0["sales"].nouns if pk0.get("sales") is not None else {}) or {}
        if nouns:
            _relabel_tree(ov, nouns)
            for i in part_items:
                for k in ("title", "detail", "metric_label", "suggestion"):
                    if isinstance(i.get(k), str):
                        i[k] = relabel(i[k], nouns)
                if isinstance(i.get("chart"), dict):
                    _relabel_tree(i["chart"], nouns)
        for i in part_items:
            i["part"] = label
            if rev and i.get("impact") and i.get("impact_share") is None:
                i["impact_share"] = min(1.0, abs(i["impact"]) / rev)
        if not ov.get("tiles") and not ov.get("sections") and not part_items:
            continue                                            # a lookup list on its own (e.g. a promotions calendar) has nothing to show
        raw += part_items
        parts.append({"name": label, "files": names, "overview": ov})
        checked["parts"].append({"name": label, "files": names, "findings": len(part_items)})
    overview = dict(parts[0]["overview"]) if parts else {"files": [], "tiles": [], "sections": [], "sources": {}, "currency": None, "currencies": []}
    if len(parts) > 1:
        overview["parts"] = [{"name": x["name"], "files": x["files"], "overview": x["overview"]} for x in parts]
        overview["files"] = [f for x in parts for f in x["overview"]["files"]]
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
        "data_check": data_check,
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
    progress("Choosing what to look into" if investigate is not None else "Checking the findings", 92)
    if investigate is None:                                   # no AI: the engine's own findings, through the same quality gates
        from .hybrid import make_investigator
        investigate = make_investigator(None, data_dir)
    try:
        report = investigate(report, frames, tables=tables, model=model)
    except TypeError:                                         # an older investigator that only takes (report, frames)
        report = investigate(report, frames)
    except Exception as e:
        report["ai"]["investigation"] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
    report["ai"]["usage"] = provider.meter.summary() if getattr(provider, "meter", None) else None
    if getattr(provider, "disabled", None):
        report["ai"]["stopped"] = provider.disabled
    report["seconds"] = round(time.time() - t0, 1)
    report = clean(report)
    out = Path(data_dir) / "analyses" / analysis_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report), encoding="utf-8")
    save_state(out / "state.pkl.gz", frames, model)
    progress("Done", 100)
    return report


def _relabel_tree(o, nouns):
    """Use the business's own words (appointments, patients, invoices...) in titles and labels."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("label", "title", "how", "name") and isinstance(v, str) and k != "name":
                o[k] = relabel(v, nouns)
            elif isinstance(v, (dict, list)) and k not in ("rows", "grains", "x", "values", "points"):
                _relabel_tree(v, nouns)
            elif k == "grains" and isinstance(v, dict):
                for g in v.values():
                    for s in g.get("series", []):
                        s["name"] = relabel(s["name"], nouns)
    elif isinstance(o, list):
        for x in o:
            _relabel_tree(x, nouns)


def _clusters(frames: dict, links: list) -> list[list[str]]:
    """Files joined by confirmed links form one part of the business; unrelated files are analysed separately."""
    parent = {n: n for n in frames}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for l in links:
        if getattr(l, "use", False) and l.child in parent and l.parent in parent:
            parent[find(l.child)] = find(l.parent)
    groups: dict = {}
    for n in frames:
        groups.setdefault(find(n), []).append(n)
    def weight(names):
        return (any(frames[n].role in ("transactions", "periodic", "lines") for n in names), sum(len(frames[n].df) for n in names))
    return sorted(groups.values(), key=weight, reverse=True)


def _part_label(sub: dict, ov: dict) -> str:
    main = ov.get("sources", {}).get("sales") or ov.get("sources", {}).get("stock") or next(iter(sub))
    base = main.split(SHEET_SEP, 1)[1] if SHEET_SEP in main else main.rsplit(".", 1)[0]
    base = base.replace("_", " ").strip()
    word = "table" if any(SHEET_SEP in n for n in sub) else "file"
    return base[:1].upper() + base[1:] if len(sub) == 1 else f"{base[:1].upper() + base[1:]} (+{len(sub) - 1} linked {word}{'s' if len(sub) > 2 else ''})"


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

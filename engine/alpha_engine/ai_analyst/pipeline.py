"""Full-AI report: what the website reads for this version."""
from __future__ import annotations
import datetime as dt
import gzip
import json
import pickle
import time
from pathlib import Path
from .brain import analyse

VERSION = "full-ai-1"


def analyze(analysis_id: str, files: list[dict], data_dir: str, provider, progress=lambda s, p: None) -> dict:
    t0 = time.time()
    progress("Reading your files", 5)
    out, tables, setup = analyse(files, provider, data_dir, progress)
    report = {"version": VERSION, "brain": "full AI", "analysis_id": analysis_id, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "files": [{"name": p["file"], "rows": p["rows"], "columns": len(p["columns"]), "withheld_personal_columns": p["withheld_personal_columns"]} for p in out["profile"]],
              "reading": {"business": out.get("business"), "columns": out.get("columns") or [], "profile": out["profile"]},
              "findings": {k: v for k, v in out.items() if k not in ("profile",)},
              "ai": {"provider": getattr(provider, "name", "none"), "model": getattr(provider, "model", None), "usage": out.get("usage"),
                     "stopped": getattr(provider, "disabled", None)},
              "limits": ["Every figure here comes from code the AI wrote and the engine ran on your rows; open 'How it was worked out' on any card to see it.",
                         "Findings describe what lines up with what. They do not prove causes.",
                         "Personal columns (names, phone numbers, emails) were removed before the AI saw anything."]}
    report["seconds"] = round(time.time() - t0, 1)
    d = Path(data_dir) / "analyses" / analysis_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text(json.dumps(report, default=str), encoding="utf-8")
    with gzip.open(d / "ai_state.pkl.gz", "wb") as fh:
        pickle.dump({"tables": tables, "setup": setup, "profile": out["profile"]}, fh, protocol=5)
    progress("Done", 100)
    return report


def load_state(analysis_dir: Path) -> dict | None:
    p = Path(analysis_dir) / "ai_state.pkl.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rb") as fh:
        return pickle.load(fh)

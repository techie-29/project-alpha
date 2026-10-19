"""Engine HTTP API. Only the Node backend talks to it (shared key, local address). Files are read from one shared folder."""
from __future__ import annotations
import os
import threading
import traceback
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from .llm import default_provider
from . import pipeline

DATA_DIR = os.environ.get("ENGINE_DATA_DIR", str(Path.cwd() / "engine_data"))
UPLOAD_DIR = os.environ.get("ENGINE_UPLOAD_DIR", str(Path.cwd().parent / "backend" / "uploads"))
API_KEY = os.environ.get("ENGINE_API_KEY", "")

app = FastAPI(title="Project Alpha engine", version="0.4.0")
JOBS: dict[str, dict] = {}


def _auth(key: str | None) -> None:
    if API_KEY and key != API_KEY:
        raise HTTPException(401, "bad engine key")


def _safe(path: str) -> str:
    p = Path(path).resolve()
    root = Path(UPLOAD_DIR).resolve()
    if root != p and root not in p.parents:
        raise HTTPException(400, "file is outside the upload folder")
    if not p.is_file():
        raise HTTPException(404, "file not found")
    return str(p)


class FileSpec(BaseModel):
    id: int | str | None = None
    name: str
    path: str


class ReadRequest(BaseModel):
    files: list[FileSpec]
    confirmations: dict = {}
    use_ai: bool = True


class AnalyzeRequest(ReadRequest):
    analysis_id: str


@app.get("/v1/health")
def health():
    return {"ok": True, "ai": default_provider().name}


@app.post("/v1/read")
def read(req: ReadRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    files = [{"id": f.id, "name": f.name, "path": _safe(f.path)} for f in req.files]
    return pipeline.read(files, req.confirmations, default_provider() if req.use_ai else None)


@app.post("/v1/analyze", status_code=202)
def analyze(req: AnalyzeRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    if JOBS.get(req.analysis_id, {}).get("status") == "running":
        raise HTTPException(409, "already running")
    files = [{"id": f.id, "name": f.name, "path": _safe(f.path)} for f in req.files]
    JOBS[req.analysis_id] = {"status": "running", "stage": "Starting", "progress": 1, "error": None}

    def run():
        try:
            from .investigate.loop import make_investigator
            provider = default_provider() if req.use_ai else None
            pipeline.analyze(req.analysis_id, files, req.confirmations, DATA_DIR, provider,
                             lambda s, p: JOBS[req.analysis_id].update(stage=s, progress=p),
                             make_investigator(provider, DATA_DIR) if provider is not None and provider.name != "none" else None)
            JOBS[req.analysis_id].update(status="done", progress=100, stage="Done")
        except Exception as e:                      # report a plain-language failure, never a stack trace
            traceback.print_exc()
            JOBS[req.analysis_id].update(status="failed", error=f"The analysis stopped: {type(e).__name__}. {str(e)[:200]}")

    threading.Thread(target=run, daemon=True).start()
    return {"accepted": True}


class AskRequest(BaseModel):
    analysis_id: str
    question: str


@app.post("/v1/ask")
def ask(req: AskRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    from .investigate.ask import ask as run_ask
    provider = default_provider()
    if provider.name == "none":
        return {"answer": None, "note": "The AI helper is not set up. Add your Gemini key to engine/.env to use Ask Alpha."}
    rp = Path(DATA_DIR) / "analyses" / Path(req.analysis_id).name / "report.json"
    import json
    report = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
    return run_ask(provider, DATA_DIR, req.analysis_id, req.question, report)


@app.get("/v1/jobs/{analysis_id}")
def job(analysis_id: str, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    j = JOBS.get(analysis_id)
    if j is None:
        rp = Path(DATA_DIR) / "analyses" / analysis_id / "report.json"
        return {"status": "done" if rp.exists() else "unknown", "stage": "Done" if rp.exists() else "", "progress": 100 if rp.exists() else 0, "error": None}
    return j


@app.get("/v1/reports/{analysis_id}")
def report(analysis_id: str, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    rp = Path(DATA_DIR) / "analyses" / Path(analysis_id).name / "report.json"
    if not rp.exists():
        raise HTTPException(404, "report not ready")
    import json
    return json.loads(rp.read_text(encoding="utf-8"))

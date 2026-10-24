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

def _load_env():
    """Read engine/.env (KEY=VALUE lines) without overriding variables that are already set."""
    f = Path(__file__).resolve().parents[1] / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
DATA_DIR = os.environ.get("ENGINE_DATA_DIR", str(Path.cwd() / "engine_data"))
UPLOAD_DIR = os.environ.get("ENGINE_UPLOAD_DIR", str(Path.cwd().parent / "backend" / "uploads"))
API_KEY = os.environ.get("ENGINE_API_KEY", "")

app = FastAPI(title="Project Alpha engine", version="0.4.0")
JOBS: dict[str, dict] = {}


def _auth(key: str | None) -> None:
    if API_KEY and key != API_KEY:
        raise HTTPException(401, "bad engine key")


def _norm(x: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(x)))


def _safe(path: str) -> str:
    p = Path(path).resolve()
    root, fp = _norm(UPLOAD_DIR), _norm(path)
    if fp != root and not fp.startswith(root.rstrip(os.sep) + os.sep):
        raise HTTPException(400, f"file is outside the upload folder. File: {path} | engine upload folder "
                                 f"(ENGINE_UPLOAD_DIR in engine/.env): {UPLOAD_DIR}")
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
    memory: dict = {}


class AnalyzeRequest(ReadRequest):
    analysis_id: str
    preferences: dict = {}


@app.get("/v1/health")
def health(deep: bool = False):
    p = default_provider()
    out = {"ok": True, "ai": p.name, "upload_dir": UPLOAD_DIR,
           "upload_dir_exists": os.path.isdir(UPLOAD_DIR), "data_dir": DATA_DIR}
    if deep and hasattr(p, "check"):
        out["ai_check"] = p.check()            # one tiny real call, to confirm the key and model work
    return out


@app.post("/v1/read")
def read(req: ReadRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    files = [{"id": f.id, "name": f.name, "path": _safe(f.path)} for f in req.files]
    return pipeline.read(files, req.confirmations, default_provider() if req.use_ai else None, req.memory)


@app.post("/v1/analyze", status_code=202)
def analyze(req: AnalyzeRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    if JOBS.get(req.analysis_id, {}).get("status") == "running":
        raise HTTPException(409, "already running")
    files = [{"id": f.id, "name": f.name, "path": _safe(f.path)} for f in req.files]
    JOBS[req.analysis_id] = {"status": "running", "stage": "Starting", "progress": 1, "error": None}

    def run():
        try:
            from .investigate.ai import make_investigator
            provider = default_provider() if req.use_ai else None
            pipeline.analyze(req.analysis_id, files, req.confirmations, DATA_DIR, provider,
                             lambda s, p: JOBS[req.analysis_id].update(stage=s, progress=p),
                             make_investigator(provider, DATA_DIR), req.preferences, req.memory)
            JOBS[req.analysis_id].update(status="done", progress=100, stage="Done")
        except Exception as e:                      # report a plain-language failure, never a stack trace
            traceback.print_exc()
            JOBS[req.analysis_id].update(status="failed", error=f"The analysis stopped: {type(e).__name__}. {str(e)[:200]}")

    threading.Thread(target=run, daemon=True).start()
    return {"accepted": True}


class ExportRequest(BaseModel):
    format: str
    report: dict
    owner: dict = {}


@app.post("/v1/export")
def export(req: ExportRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    from fastapi.responses import Response
    from .report.export import to_pdf, to_xlsx
    if req.format == "pdf":
        return Response(to_pdf(req.report, req.owner), media_type="application/pdf")
    if req.format == "xlsx":
        return Response(to_xlsx(req.report, req.owner), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    raise HTTPException(400, "format must be pdf or xlsx")


class AskRequest(BaseModel):
    analysis_id: str
    question: str
    history: list = []


@app.post("/v1/ask")
def ask(req: AskRequest, x_engine_key: str | None = Header(default=None)):
    _auth(x_engine_key)
    from .investigate.ask import ask as run_ask
    provider = default_provider()
    if provider.name == "none":
        return {"answer": None, "note": "The AI helper is not set up. Add OPENROUTER_API_KEY (or GEMINI_API_KEY) to engine/.env to use Ask Alpha."}
    rp = Path(DATA_DIR) / "analyses" / Path(req.analysis_id).name / "report.json"
    import json
    report = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
    return run_ask(provider, DATA_DIR, req.analysis_id, req.question, report, req.history)


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

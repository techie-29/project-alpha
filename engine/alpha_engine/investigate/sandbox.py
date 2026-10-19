"""Runs model-written pandas code in a separate, restricted process.
Not a hardened container: the protections are (1) an AST allow-list (no imports, no dunder access, no file/network/eval calls),
(2) a stripped set of builtins, (3) CPU / memory / file-size limits and a wall-clock timeout, (4) only the prepared table is passed in."""
from __future__ import annotations
import ast
import json
import os
import pickle
import subprocess
import sys
import tempfile

BANNED_NODES = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Global, ast.Nonlocal,
                ast.Await, ast.Yield, ast.YieldFrom, ast.Delete, ast.With, ast.AsyncWith, ast.Try, ast.Raise)
BANNED_NAMES = {"open", "exec", "eval", "compile", "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir", "input",
                "breakpoint", "help", "type", "object", "__import__", "memoryview", "bytearray", "exit", "quit", "os", "sys", "subprocess"}
BANNED_ATTRS = {"eval", "query", "exec", "system", "popen", "open", "load", "loads", "save", "memmap", "fromfile", "tofile", "style", "plot",
                "to_csv", "to_pickle", "to_excel", "to_json", "to_parquet", "to_sql", "to_hdf", "to_clipboard", "to_feather", "to_stata",
                "to_html", "to_latex", "to_markdown", "to_xml", "to_orc", "to_gbq", "pipe", "ctypeslib", "lib", "testing", "compat"}
MAX_CODE = 4000


class Rejected(ValueError):
    pass


def check(code: str) -> ast.AST:
    if not isinstance(code, str) or not code.strip():
        raise Rejected("no code")
    if len(code) > MAX_CODE:
        raise Rejected("code too long")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise Rejected(f"syntax error: {e.msg}")
    for n in ast.walk(tree):
        if isinstance(n, BANNED_NODES):
            raise Rejected(f"{type(n).__name__} is not allowed")
        if isinstance(n, ast.Name) and (n.id in BANNED_NAMES or (n.id.startswith("__"))):
            raise Rejected(f"name '{n.id}' is not allowed")
        if isinstance(n, ast.Attribute) and (n.attr.startswith("_") or n.attr in BANNED_ATTRS or n.attr.startswith("read_")):
            raise Rejected(f"attribute '{n.attr}' is not allowed")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and ("__" in n.value or len(n.value) > 200):
            raise Rejected("suspicious string")
    return tree


RUNNER = r'''
import sys, json, pickle, resource, ast
mem, cpu = int(sys.argv[2]), int(sys.argv[3])
resource.setrlimit(resource.RLIMIT_AS, (mem, mem)); resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu)); resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
import pandas as pd, numpy as np
payload = pickle.load(open(sys.argv[1], "rb"))
code = payload["code"]
SAFE = {k: __builtins__.__dict__[k] if hasattr(__builtins__, "__dict__") else __builtins__[k] for k in
        ["abs","all","any","bool","dict","enumerate","float","int","len","list","max","min","range","round","set","sorted","str","sum","tuple","zip","isinstance","map","filter","reversed","divmod","pow","True","False","None","ValueError","KeyError","Exception"]}
env = {"__builtins__": SAFE, "pd": pd, "np": np, "df": payload["df"], "result": None}
exec(compile(ast.parse(code), "<alpha>", "exec"), env)
def conv(o, depth=0):
    if isinstance(o, pd.DataFrame):
        o = o.head(40)
        return {"columns": [str(c) for c in o.columns], "rows": [[conv(v, 1) for v in r] for r in o.itertuples(index=False, name=None)]}
    if isinstance(o, pd.Series):
        return {str(k): conv(v, 1) for k, v in o.head(40).items()}
    if isinstance(o, dict):
        return {str(k): conv(v, depth + 1) for k, v in list(o.items())[:40]}
    if isinstance(o, (list, tuple, set)):
        return [conv(v, depth + 1) for v in list(o)[:40]]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_, bool)): return bool(o)
    if isinstance(o, (int, str)) or o is None: return o
    if isinstance(o, pd.Timestamp): return o.date().isoformat()
    return str(o)[:80]
sys.stdout.write("\n@@RESULT@@" + json.dumps(conv(env["result"])))
'''


def run(code: str, df, timeout: int = 25, memory_mb: int = 3000, cpu_s: int = 20) -> dict:
    """Returns {"ok": True, "result": ...} or {"ok": False, "error": plain text}."""
    try:
        check(code)
    except Rejected as e:
        return {"ok": False, "error": f"The code was not allowed to run: {e}."}
    with tempfile.TemporaryDirectory() as d:
        pk = os.path.join(d, "in.pkl")
        with open(pk, "wb") as fh:
            pickle.dump({"code": code, "df": df}, fh, protocol=5)
        try:
            p = subprocess.run([sys.executable, "-I", "-c", RUNNER, pk, str(memory_mb * 1024 * 1024), str(cpu_s)], capture_output=True, text=True,
                               timeout=timeout, cwd=d, env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1"})
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "The calculation took too long and was stopped."}
    if p.returncode != 0 or "@@RESULT@@" not in p.stdout:
        last = (p.stderr.strip().splitlines() or ["failed"])[-1][:200]
        return {"ok": False, "error": f"The calculation failed: {last}"}
    try:
        return {"ok": True, "result": json.loads(p.stdout.split("@@RESULT@@", 1)[1])}
    except Exception:
        return {"ok": False, "error": "The calculation returned something unreadable."}

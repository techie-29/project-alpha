"""Run Project Alpha's engine on your files without the website or any database, and print what it finds.

Usage (from the project's engine folder, with its virtual environment active):
    python try_alpha.py  file1.csv [file2.xlsx ...]            -> full report, AI on if a key is in engine/.env
    python try_alpha.py  --no-ai  file1.csv                    -> the same without the AI helper
    python try_alpha.py  file1.csv --ask "Which product should I stock more of?" --ask "Why did sales fall?"

Output goes to the screen and to ./alpha_try/<name>/analyses/try_<name>/report.json (a readable copy is in ./alpha_try/<name>/report.txt). Nothing is sent anywhere except,
if you have set OPENROUTER_API_KEY in engine/.env, summaries (column names, statistics, findings) to OpenRouter.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
env = ENGINE / ".env"
if env.exists():                                   # same .env reading as the engine itself
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from alpha_engine import pipeline                  # noqa: E402
from alpha_engine.llm import default_provider, NullProvider   # noqa: E402
from alpha_engine.investigate.ai import make_investigator     # noqa: E402


def money(v):
    return f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)


def show(report, out):
    L = []
    P = L.append
    b = report["briefing"]
    P("=" * 78)
    P("BRIEFING")
    P("=" * 78)
    P(b["headline"])
    P(b["coverage"])
    for k in b["key_numbers"]:
        P("  - " + k)
    ai = report.get("ai", {})
    P(f"\nAI provider: {ai.get('provider')}   investigation: {ai.get('investigation')}   "
      f"{('error: ' + ai['investigation_error']) if ai.get('investigation_error') else ''}")
    P("\nHOW THE FILES WERE READ")
    for f in report["reading"]["files"]:
        P(f"  {f['name']}  [{f.get('role')}]  rows={f.get('rows')}  time column={f.get('time_col')}")
        for c in f["columns"]:
            P(f"      {c['name']:<28} -> {str(c.get('label') or c.get('concept') or 'not used'):<26} confidence {c.get('confidence')}")
        for n in f.get("notes", [])[:8]:
            P(f"      note: {n}")
    P("\nDASHBOARD NUMBERS")
    ov = report["overview"]
    for t in ov.get("tiles", []):
        P(f"  {t['label']:<28} {money(t['value'])} {t.get('unit') or ''}")
    for part in ov.get("parts", []) or []:
        P(f"  -- part: {part['name']}")
        for t in part["overview"].get("tiles", []):
            P(f"     {t['label']:<28} {money(t['value'])} {t.get('unit') or ''}")
    P("\nTOP FINDINGS")
    items = [i for i in report["insights"]["items"] if not i.get("muted")]
    for n, i in enumerate(items[:25], 1):
        tag = "  [AI]" if i["type"] == "ai_question" else ""
        P(f"{n:>2}. ({i['type']}, {i['strength']}, {i['polarity']}, score {i['score']}){tag}")
        P(f"    {i['title']}")
        P(f"    {i['detail']}")
        if i.get("ai_note"):
            P(f"    AI note: {i['ai_note']}")
        if i.get("calculations"):
            for c in i["calculations"][:3]:
                P(f"    calculation: {c.get('why')}  ->  {json.dumps(c.get('result'))[:300]}")
    P(f"\n({len(items)} findings in total)")
    if report["insights"]["checked"].get("failed"):
        P("\nANALYSES THAT FAILED: " + "; ".join(report["insights"]["checked"]["failed"]))
    P("\nQUESTIONS FOR THE OWNER")
    for q in report.get("questions", [])[:8]:
        P("  - " + (q.get("question") or str(q)))
    text = "\n".join(L)
    (out / "report.txt").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--ask", action="append", default=[])
    a = ap.parse_args()
    name = Path(a.files[0]).stem[:40]
    out = Path("alpha_try") / name
    out.mkdir(parents=True, exist_ok=True)
    provider = NullProvider() if a.no_ai else default_provider()
    print(f"AI provider: {provider.name}")
    files = [{"id": i + 1, "name": Path(p).name, "path": str(Path(p).resolve())} for i, p in enumerate(a.files)]
    t0 = time.time()
    last = [""]

    def progress(stage, pct):
        if stage != last[0]:
            print(f"  [{pct:>3}%] {stage}")
            last[0] = stage

    aid = "try_" + name
    report = pipeline.analyze(aid, files, {}, str(out), provider, progress,
                              make_investigator(provider, str(out)) if provider.name != "none" else None)
    print(f"\nFinished in {time.time() - t0:.0f} seconds. Saved: {out / 'analyses' / aid / 'report.json'}\n")
    show(report, out)
    if a.ask:
        if provider.name == "none":
            print("\nAsk Alpha needs an AI key; skipped.")
            return
        from alpha_engine.investigate.ask import ask
        hist = []
        lines = []
        for q in a.ask:
            r = ask(provider, str(out), aid, q, report, hist)
            lines += ["", "=" * 78, "QUESTION: " + q, "=" * 78, json.dumps(r, indent=2, ensure_ascii=False)]
            hist.append({"q": q, "a": r.get("answer") or ""})
        txt = "\n".join(lines)
        (out / "ask.txt").write_text(txt, encoding="utf-8")
        print(txt)


if __name__ == "__main__":
    main()

"""Metric + AI version. Run Project Alpha's engine on your files without the website or any database, and print what it finds.

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
from alpha_engine.hybrid import make_investigator, ask      # noqa: E402


def money(v):
    return f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)


def show_cards(f, L):
    P = L.append
    for n, c in enumerate(f.get("cards", []), 1):
        m = c.get("money") or {}
        P(f"{n:>2}. [{c.get('tone')}, {c.get('strength')}, {c.get('source')}] {c['headline']}")
        for p in c.get("points", []):
            P(f"      - {p}")
        if m.get("amount") is not None:
            P(f"      money: {money(m['amount'])} {m.get('what') or ''}")
        if c.get("look_into"):
            P(f"      worth looking into: {c['look_into']}")
        for h in c.get("how", [])[:3]:
            P(f"      from: {h.get('question')}  |  {h.get('formula') or ''}")
    if f.get("dropped"):
        P(f"\nHELD BACK BY THE CHECKS ({len(f['dropped'])})")
        for d in f["dropped"][:20]:
            P(f"  - {d.get('headline')}: {'; '.join(d.get('why') or [])}")


def show(report, out):
    L = []
    P = L.append
    f = report.get("findings") or {}
    P("=" * 78); P("SUMMARY  (" + str(f.get("brain")) + ")"); P("=" * 78)
    P(f.get("headline") or report.get("briefing", {}).get("headline") or "")
    if f.get("understanding"):
        P(f["understanding"])
    if f.get("error"):
        P("AI problem: " + f["error"])
    u = (report.get("ai") or {}).get("usage") or {}
    P(f"AI: {(report.get('ai') or {}).get('provider')}  calls {u.get('calls')}  tokens in/out {u.get('tokens_in')}/{u.get('tokens_out')}  cost ${u.get('cost_usd')}"
      f"  {'(replayed from the saved run)' if f.get('replayed') else ''}")
    for s in f.get("steps", []):
        P(f"  step {s['step']}: {s['ok']} of {s['asked']} requests ran")
    P("\nKEY FIGURES")
    for t in (report.get("overview") or {}).get("tiles", [])[:10]:
        P(f"  {t['label']:<34} {money(t['value'])} {t.get('unit') or ''}")
    dc = report.get("data_check") or {}
    P("\nDATA CHECK: " + str(dc.get("headline")))
    for fl in dc.get("files", []):
        for c in fl["checks"]:
            if c["status"] in ("warn", "fail", "fixed"):
                P(f"  [{c['status']}] {c['title']}: {c['detail'][:220]}")
    P("\nFINDINGS")
    show_cards(f, L)
    text = "\n".join(L)
    (out / "report.txt").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore the saved AI run for these files and ask the AI again")
    ap.add_argument("--ask", action="append", default=[])
    a = ap.parse_args()
    if a.fresh:
        os.environ["AI_REPLAY"] = "0"
    name = Path(a.files[0]).stem[:40]
    out = Path("alpha_try") / name
    out.mkdir(parents=True, exist_ok=True)
    provider = NullProvider() if a.no_ai else default_provider()
    print(f"AI provider: {provider.name} {getattr(provider, 'model', '')}")
    files = [{"id": i + 1, "name": Path(p).name, "path": str(Path(p).resolve())} for i, p in enumerate(a.files)]
    t0 = time.time()
    last = [""]

    def progress(stage, pct):
        if stage != last[0]:
            print(f"  [{pct:>3}%] {stage}")
            last[0] = stage

    aid = "try_" + name
    report = pipeline.analyze(aid, files, {}, str(out), provider, progress, make_investigator(provider if provider.name != "none" else None, str(out)))
    print(f"\nFinished in {time.time() - t0:.0f} seconds. Saved: {out / 'analyses' / aid / 'report.json'}\n")
    show(report, out)
    if a.ask:
        if provider.name == "none":
            print("\nAsk Alpha needs an AI key; skipped.")
            return
        frames = pipeline.load_state(out / "analyses" / aid / "state.pkl.gz")
        hist, lines = [], []
        for q in a.ask:
            r = ask(provider, frames, report, q, hist)
            lines += ["", "=" * 78, "QUESTION: " + q, "=" * 78, json.dumps({k: v for k, v in r.items() if k != "calculations"}, indent=2, ensure_ascii=False),
                      f"({len(r.get('calculations') or [])} calculations; AI calls so far {provider.meter.calls}, cost ${provider.meter.cost:.4f})"]
            hist.append({"question": q})
        txt = "\n".join(lines)
        (out / "ask.txt").write_text(txt, encoding="utf-8")
        print(txt)


if __name__ == "__main__":
    main()

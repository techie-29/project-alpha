# Project Alpha

A business-intelligence website for any business. Upload raw CSV or Excel files (one or many, linked or separate). Alpha works out what each column means, scans every measure by group by time window for what changed, shows the evidence, and tells you what to fix, keep and watch. It never claims a cause.

## How it is built

| Layer | Folder | What it does |
|---|---|---|
| Website | `frontend/` | React + Vite. Sign in, upload, "how I read your files" review, progress, Briefing / Your data / Insights / Intelligence, Ask Alpha, PDF and Excel export. |
| API | `backend/` | Node + Express + MySQL. Accounts, JWT, file storage, analysis jobs, saved reports, owner feedback, export. Checks the account on every request. |
| Engine | `engine/` | Python + FastAPI. Understands columns, links files, scans for changes with shuffle tests, finds drivers, builds the report, runs the AI investigation and Ask Alpha. Listens on 127.0.0.1 only. |

Privacy: the AI helper (Gemini) is only sent findings, summaries, column names and statistics. Raw rows and personal columns are never sent. Code written by the AI runs in a restricted process and every number in its wording is checked against what the code produced.

## 1. Prepare MySQL

Fresh database: run `backend/database/schema.sql` in MySQL Workbench.

Existing database: run `backend/database/admin_control_migration.sql` (if not done), `006_v3_business_preferences.sql` (if not done) and `007_alpha_engine.sql`. The old retail tables are no longer used and can be dropped.

## 2. Backend

```bash
cd backend
cp .env.example .env      # then fill in your MySQL details, JWT_SECRET and ENGINE_API_KEY
npm install
npm start                 # http://localhost:5000
```

## 3. Engine

```bash
cd engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env      # then set ENGINE_API_KEY (same as backend), the two folders, and GEMINI_API_KEY
uvicorn alpha_engine.api:app --host 127.0.0.1 --port 8001
```

Without a Gemini key everything still works; only the AI column review, AI investigation notes and Ask Alpha are off.

## 4. Website

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

Set `VITE_API_BASE_URL` if the backend is not on `http://localhost:5000`.

## 5. Try it

Register a business account, choose **New analysis**, upload your files, check the "how I read your files" table (change anything that is wrong), and run. Large files (about 150,000 rows) take a few minutes; you can leave the page.

## Tests

```bash
cd engine/tests && PYTHONPATH=.. python3 -m pytest -q .     # engine, about a minute
cd backend && npx vitest run
cd frontend && npx vitest run
```

## Honest limits

- Statistical minimums are hand-set: 30 rows per group, 3 rows per period, 4 periods per side, at least 12 periods, 5 rows per period to confirm a change.
- Amounts in different currencies are analysed separately, never added.
- Findings show what changed and what it lines up with. They do not prove a cause. Labels: Calculated, Supported by evidence, Possible (early sign).
- Tested on synthetic data and the practice files; calibration on real owners' files is still to come.
- The code sandbox is a restricted process (allow-listed code, resource limits), not a hardened container. Run the engine on a machine you control.

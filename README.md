# Project Alpha

A business-intelligence website for any business. Upload raw CSV or Excel files (one or many, linked or separate). Alpha works out what each column means, scans every measure by group by time window for what changed, shows the evidence, and tells you what to fix, keep and watch. It never claims a cause.

## How it works

1. **Read.** Any CSV/Excel export: separators, title lines above the header, decimal commas, %, currency symbols, "N/A" blanks, mixed casing, duplicates, Excel header offsets. Every fix is listed.
2. **Understand the business.** Each column gets a business meaning (revenue, cost, units, stock on hand, customer, product, delivery days, rating...) from its values, arithmetic between columns (units x price = amount, sales - cost = profit), the kind of file (activity log, line items, master list, stock snapshot) and fuzzy name matching. The AI only reviews unsure columns, and code checks its answer against the values. You confirm or correct it on "How I read your files"; Alpha remembers your choices.
3. **Overview.** Headline numbers that fit your data, with month-on-month and year-on-year changes, and charts by day / week / month / quarter / year, breakdowns, rankings and distributions for every business area. Linked files are one business; unlinked files are summarised separately and never mixed.
4. **Analyses.** Group differences, hidden combinations (open search), trends, seasonality, weekly rhythm, mix shifts, relationships, concentration, customers who stopped coming back, stock-outs / dead stock / days of cover, loss makers, data checks, and the change-over-time scan. Everything is shuffle-tested and labelled.
5. **Insights and suggestions.** Ranked by money involved, strength, actionability and your feedback; merged into stories; Fix / Keep / Plan / Watch.
6. **AI helper (optional).** Proposes its own questions for your files and answers them with checked calculations, explains top findings, and powers Ask Alpha. Every number it writes must come from a calculation; causal claims are refused.

| Layer | Folder | What it does |
|---|---|---|
| Website | `frontend/` | React + Vite: upload, business review, Briefing, Overview, Insights, Suggestions, Ask Alpha, Coverage, PDF / Excel export. |
| API | `backend/` | Node + Express + MySQL: accounts, files, analysis jobs, saved reports, feedback, remembered column meanings, Ask history. |
| Engine | `engine/` | Python + FastAPI (127.0.0.1 only): everything above. |

Privacy: the AI helper is sent column names, statistics, finding summaries and aggregated results. Never raw rows, personal columns or free text.

## 1. Prepare MySQL

Fresh database: run `backend/database/schema.sql` in MySQL Workbench.

Existing database: run `backend/database/admin_control_migration.sql` (if not done), `006_v3_business_preferences.sql` (if not done), `007_alpha_engine.sql` and `008_alpha_memory_questions.sql`. The old retail tables are no longer used and can be dropped.

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
pip install pandas numpy scipy openpyxl reportlab fastapi uvicorn python-multipart
pip install pyarrow        # optional, faster file reading
cp .env.example .env      # then set ENGINE_API_KEY (same as backend), the two folders, and GEMINI_API_KEY
uvicorn alpha_engine.api:app --host 127.0.0.1 --port 8001
```

Without a Gemini key everything still works; only the AI column review, the AI's own questions and notes, and Ask Alpha are off.

To check the key works, open http://127.0.0.1:8001/v1/health?deep=true. It makes one tiny real call and reports `ai_check`.

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

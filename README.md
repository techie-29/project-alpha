# Project Alpha

Project Alpha currently combines:

- Module 1: validated MySQL business registration, login, JWT sessions, security headers, rate limits, and protected APIs.
- Module 2: multi-file CSV/Excel batches, hashing and duplicate detection, extraction, profiling, dataset classification, persistent per-file progress, and paginated React previews.
- Module 3: canonical header mapping with aliases, fuzzy/value matching, confidence reasons, collision prevention, manual confirmation, and reusable templates.
- Module 4: deterministic validation, repairs, skipped-row evidence, issue persistence, and validation summaries.
- Modules 5–6: normalized transformations, computed revenue/profit, typed structured storage, and explainable quality scores.
- Module 7: adaptive KPIs, period comparisons, latest-stock logic, ABC, RFM, anomalies, statistical forecast/backtest, and a modular rule-based insight engine.
- Module 8: executive and detailed dashboards, provenance, filters, source traceability, dataset inclusion controls, overlap/repeated-order warnings, CSV/Excel exports, and printable reports.

## 1. Prepare MySQL

For a fresh database, run `backend/database/schema.sql` in MySQL Workbench.

For an existing Project Alpha database, run these migrations in order:

1. `backend/database/001_v3_ingestion_foundation.sql`
2. `backend/database/002_v3_ingestion_batches.sql`
3. `backend/database/003_v3_header_mapping.sql`
4. `backend/database/004_v3_validation.sql`
5. `backend/database/005_v3_transformation_storage.sql`

## 2. Configure the backend

Copy `backend/.env.example` to `backend/.env` and replace the example values with your local MySQL credentials and a long JWT secret.

```bash
cd backend
npm install
npm start
```

The backend runs at `http://localhost:5000`.

## 3. Run the React frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

## 4. Test the integrated flow

1. Create a business account.
2. Sign in (registration also starts a signed-in session).
3. Select up to 10 `.csv`, `.xlsx`, or `.xls` datasets, each smaller than 10 MB and 50,000 rows.
4. Start the batch and confirm each file reaches its own completed or failed state.
5. Check file metadata, detected dataset type, skipped-row count, structure, and paginated preview.
6. Continue to mapping, review confidence/reasons, correct a mapping, and confirm it.
7. Upload the same header structure later and confirm the saved template is reused.
8. Run validation and inspect valid, repaired, and skipped rows plus their reasons.
9. Run transformation and inspect structured record counts, examples, and the quality-score breakdown.
10. Open the dashboard and verify the provenance panel appears before KPIs and charts.
11. Select Revenue, Units, or Inventory to trace the metric to normalized records and original source rows.
12. Review sales, product ABC, inventory days-of-cover, customer RFM, insights, anomalies, and forecast backtest evidence.
13. Exclude a dataset in the Dataset Library and confirm the next analytics request recalculates without it.
14. Export normalized CSV/Excel data or an issue report and print the executive summary.
15. Upload the same file again and confirm duplicate content is rejected without affecting other files in the batch.
16. Sign out and confirm the protected workspace is no longer accessible.

## 5. Analytics APIs

All routes below require `Authorization: Bearer <token>` and are scoped from the verified account, never from a client-provided business ID.

- `GET /api/analytics/overview` — provenance, KPIs, charts, detailed analytics, and intelligence.
- `GET /api/analytics/{sales|products|inventory|customers|insights}` — purpose-specific responses.
- `GET /api/analytics/trace/{revenue|units|stock}` — metric-to-source evidence.
- `GET /api/datasets` and `GET /api/datasets/:id` — dataset library and detail.
- `PATCH /api/datasets/:id/inclusion` — include or exclude a dataset from subsequent analytics.
- `GET /api/datasets/:id/export?type=sales|stock|issues&format=csv|xlsx` — normalized and issue exports.

Analytics routes accept `preset=daily|weekly|monthly|quarterly|custom`, custom `from`/`to` dates, and applicable `datasetId`, `product`, `category`, `customer`, and `status` filters.

## 6. Run verification

```bash
cd backend
npm test

cd ../frontend
npm run build
```

The deterministic fixtures live in `backend/src/tests/fixtures`. Rebuild them with `node src/tests/fixtures/generateFixtures.cjs` from the backend folder.

The automated suite covers ingestion fixtures, mapping, validation, transformation, quality scoring, KPI calculations, tenant scoping, latest inventory snapshots, every insight rule, forecast guards/backtest, RFM/ABC boundaries, dataset controls, traceability, and exports. A live MySQL end-to-end run still requires the local `backend/.env` described above.

Never commit `backend/.env`, `node_modules`, uploaded files, or database passwords.

# Project Alpha

Project Alpha currently combines:

- Module 1: MySQL business registration, login, JWT sessions, and protected APIs.
- Module 2: multi-file CSV/Excel batches, hashing and duplicate detection, extraction, profiling, dataset classification, persistent per-file progress, and paginated React previews.
- Module 3 foundation: canonical fields plus alias, fuzzy, confidence/reason, and basic value-sniffing engines. The final mapping workflow follows after Module 2 verification.

## 1. Prepare MySQL

For a fresh database, run `backend/database/schema.sql` in MySQL Workbench.

For an existing Project Alpha database, run these migrations in order:

1. `backend/database/001_v3_ingestion_foundation.sql`
2. `backend/database/002_v3_ingestion_batches.sql`
3. `backend/database/003_v3_header_mapping.sql`

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
8. Upload the same file again and confirm duplicate content is rejected without affecting other files in the batch.
9. Sign out and confirm the upload workspace is no longer accessible.

## 5. Run verification

```bash
cd backend
npm test

cd ../frontend
npm run build
```

The deterministic fixtures live in `backend/src/tests/fixtures`. Rebuild them with `node src/tests/fixtures/generateFixtures.cjs` from the backend folder.

Never commit `backend/.env`, `node_modules`, uploaded files, or database passwords.

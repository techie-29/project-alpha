# Project Alpha V3 Test Plan

## Module 2 automated coverage

- Table normalization: duplicate/blank headers, structural row skips, source row numbers, row limit.
- CSV/Excel parsing: UTF-8 BOM, blank rows, first-sheet policy, merged headers, formatted Excel dates.
- Profiling and classification: sales, inventory, customer, and supplier fixtures.
- Dataset service: SHA-256 hash, duplicate short-circuit, parse/profile/classify/persistence handoff.
- Batch service: partial success and continued processing after a duplicate/file failure.
- Upload API: multipart batch contract, empty batch rejection, account-scoped progress lookup.
- Frontend: production build and manual queue-state verification.

## Module 3 automated coverage

- Exact aliases, fuzzy suggestions, value-sniff fallback, and duplicate-target prevention.
- Required-field coverage and missing-critical-field reporting.
- Stable header signatures, saved-template reuse, manual confirmation, and mapping validation.
- Account-scoped mapping API load and confirmation contracts.

## Manual MySQL/API verification

1. Apply schema or migrations 001 and 002.
2. Register and sign in as a business.
3. Upload `sales_clean.csv`, `inventory.xlsx`, and `customers.csv` together.
4. Confirm the queue shows three independent results and the Excel first-sheet warning.
5. Confirm one `ingestion_batches` row, three `ingestion_batch_items` rows, three `ingestions` rows, and expected `ingestion_rows` counts.
6. Upload a batch containing one previous file and one new file. Confirm partial status, duplicate error on only the repeated file, and persistence of the new file.
7. Sign in as another business and verify `GET /api/upload/batches/:batchId` returns 404 for the first business's batch.

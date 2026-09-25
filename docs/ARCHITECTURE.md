# Project Alpha V3 Architecture

This document is the implementation contract for the upgraded Project Alpha.

## Core flow

Register/Login -> Upload -> Profile -> Map -> Validate -> Transform -> Store -> Analyze -> Act

## Layering rule

1. React UI renders state and calls APIs.
2. Express routes authenticate, validate requests, and delegate.
3. Services orchestrate database work and pure engine functions.
4. The engine contains framework-independent business/data logic only.
5. MySQL stores account-scoped source, normalized, validation, mapping, and audit data.

## Pure engine areas

- ingestion: parseFile, profileColumns, hashFile
- mapping: canonical fields, aliases, similarity, suggestions
- validation: small rule registry + validateRows
- transform: normalizers + transformRows
- quality: quality score
- analytics: KPIs, comparisons, products, inventory, customers, highlights
- forecast: forecast, backtest, anomaly
- insights: config, registry, one rule per file

Engine files must not import Express, React, MySQL, or network clients.

## Security contract

Every business-owned query is scoped by the authenticated account from the verified JWT. Never trust a business ID from request parameters or body for authorization.

## Data trust contract

- Preserve raw rows.
- Preserve normalized records.
- Preserve mapping and repair decisions.
- Missing data produces unavailable analytics, not fake zeroes.
- Revenue, units, and stock must be traceable back to source rows.
- Compatible datasets may be combined only with duplicate/overlap controls.

## Upgrade strategy

The current Modules 1-3 remain the working baseline. New engine modules are introduced beside them first, tested, then routes/services are migrated incrementally. main must remain demo-safe.

## Module 2 batch contract

- `POST /api/upload` remains the backward-compatible single-file endpoint.
- `POST /api/upload/batch` accepts the multipart field `files` with 1-10 CSV/XLS/XLSX files.
- Every file has a 10 MB and 50,000 extracted-row limit.
- Files are hashed, duplicate-checked, parsed, profiled, classified, and persisted independently. One failure never rolls back another file.
- `ingestion_batches` stores persistent totals and final state. `ingestion_batch_items` stores ordered per-file state, ingestion link, and safe error details.
- `GET /api/upload/batches/:batchId` is scoped to the authenticated business and restores persisted progress.
- The frontend queue uses `queued -> uploading -> processing -> completed|failed`. A completed ingestion hands off as `ready_for_mapping`.
- Excel uses the first worksheet only, reports ignored worksheets, repairs common two-level merged headers, and converts formatted Excel dates to ISO date strings.

# Project Alpha V3 Decisions

- 2026-09-25: Keep the existing project and upgrade it; do not restart from zero.
- 2026-09-25: Keep main demo-safe; V3 work begins on refactor/alpha-v3-foundation.
- 2026-09-25: Fixed stack remains JavaScript, React/Vite, Node/Express, JWT, MySQL.
- 2026-09-25: Introduce a pure engine layer before Module 4.
- 2026-09-25: Existing Modules 1-3 are migrated incrementally instead of rewritten in one large change.
- 2026-09-25: Mapping suggestions expose confidence and reason; the user remains the final authority.
- 2026-09-25: Missing analytical inputs produce unavailable states, never invented zero values.
- 2026-09-25: Existing CommonJS runtime remains temporarily during the non-breaking foundation slice; ES module conversion will be a dedicated migration after tests are in place.
- 2026-09-25: Module 2 batches accept at most 10 files; limits are 10 MB and 50,000 extracted rows per file.
- 2026-09-25: Batch files are processed independently and persisted in `ingestion_batches` plus `ingestion_batch_items`; partial success is an expected result, not a request-level failure.
- 2026-09-25: Excel processing remains isolated behind `fileprocessingservices.js`; only the first worksheet is ingested and ignored sheets are reported.
- 2026-09-25: Module 2 ends at `ready_for_mapping`; automatic Module 3 execution was removed from the upload button so each module can be tested and explained separately.
- 2026-09-25: Confirmed mappings are stored once per ingestion as JSON; reusable templates are business-scoped and keyed by a normalized header-set hash.
- 2026-09-25: Mapping coverage measures dataset-type critical field groups, with explicit alternatives, while header coverage is reported separately.
- 2026-09-25: Ambiguous numeric dates are decided from column-wide evidence; when order remains unresolved, affected rows are skipped with `AMBIGUOUS_DATE_FORMAT` instead of being guessed.
- 2026-09-25: Validation persists all row outcomes and issues, but API/UI previews are capped (50 rows and 200 issues) so large files do not freeze the browser.

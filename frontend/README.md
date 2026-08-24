# Project Alpha — Module 2 Frontend

Canonical React + Vite frontend for the Data Ingestion module. It contains no backend and no fake API response.

## Run locally

```bash
npm install
npm run dev
```

The app uses `http://localhost:5000/api/upload` by default. To change it, copy `.env.example` to `.env` and update `VITE_UPLOAD_API_URL`.

## Upload contract

`src/services/uploadApi.js` creates `FormData`, appends the selected file under the exact field name `file`, and sends a `POST` request. It deliberately does not set `Content-Type`; the browser supplies the multipart boundary.

The result adapter accepts common response variants, including:

```json
{
  "success": true,
  "rowCount": 3,
  "data": [
    { "columnA": "value", "columnB": 10 }
  ]
}
```

It also supports `rows`, `preview`, explicit `headers`/`columns`, nested `result`/`dataset` objects, file metadata, sheet names, and richer column profiles using `detectedType`/`type` plus `missingCount`/`nullCount`.

## JWT integration

`uploadDataset(file, jwtToken)` already accepts an optional token. When Module 1 is connected, retrieve its token in `src/App.jsx` and pass it as the second argument. The service adds `Authorization: Bearer <JWT>` only when a token exists.

## Scope boundary

Dashboard, Analytics, Insights, and Settings navigation are intentionally disabled. “Continue to Header Mapping” is also disabled. Those features belong to future modules.

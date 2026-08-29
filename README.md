# Project Alpha

Project Alpha currently combines:

- Module 1: MySQL business registration, login, JWT sessions, and protected APIs.
- Module 2: CSV/Excel upload, extraction, technical profiling, and paginated React preview.

## 1. Prepare MySQL

Run `backend/database/schema.sql` in MySQL Workbench.

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
3. Upload a `.csv`, `.xlsx`, or `.xls` dataset smaller than 10 MB.
4. Check file metadata, dataset structure, and the five-row paginated preview.
5. Sign out and confirm the upload workspace is no longer accessible.

Never commit `backend/.env`, `node_modules`, uploaded files, or database passwords.

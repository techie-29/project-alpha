const express = require("express");
const db = require("../config/db");

const router = express.Router();

router.get("/dashboard", async (req, res, next) => {
    try {
        const [[accountStats]] = await db.execute(`
            SELECT
                COUNT(*) AS totalAccounts,
                SUM(role = 'admin') AS adminAccounts,
                SUM(role = 'user') AS businessAccounts
            FROM business_accounts
        `);
        const [[ingestionStats]] = await db.execute(`
            SELECT
                COUNT(*) AS totalUploads,
                COALESCE(SUM(row_count), 0) AS totalRows,
                COALESCE(SUM(column_count), 0) AS totalColumns
            FROM ingestions
        `);
        const [recentUploads] = await db.execute(`
            SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat,
                   i.row_count AS rowCount, i.column_count AS columnCount, i.status,
                   i.created_at AS createdAt, b.business_name AS businessName, b.email
            FROM ingestions i
            JOIN business_accounts b ON b.id = i.business_account_id
            ORDER BY i.created_at DESC
            LIMIT 8
        `);

        return res.json({
            success: true,
            data: {
                stats: { ...accountStats, ...ingestionStats },
                recentUploads
            }
        });
    } catch (error) { next(error); }
});

router.get("/users", async (req, res, next) => {
    try {
        const [users] = await db.execute(`
            SELECT b.id, b.business_name AS businessName, b.email, b.role, b.created_at AS createdAt,
                   COUNT(i.id) AS uploadCount
            FROM business_accounts b
            LEFT JOIN ingestions i ON i.business_account_id = b.id
            GROUP BY b.id, b.business_name, b.email, b.role, b.created_at
            ORDER BY b.created_at DESC
        `);
        return res.json({ success: true, data: { users } });
    } catch (error) { next(error); }
});

router.get("/datasets", async (req, res, next) => {
    try {
        const [datasets] = await db.execute(`
            SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat,
                   i.file_size_bytes AS fileSizeBytes, i.sheet_name AS sheetName,
                   i.row_count AS rowCount, i.column_count AS columnCount,
                   i.status, i.created_at AS createdAt,
                   b.business_name AS businessName, b.email
            FROM ingestions i
            JOIN business_accounts b ON b.id = i.business_account_id
            ORDER BY i.created_at DESC
        `);
        return res.json({ success: true, data: { datasets } });
    } catch (error) { next(error); }
});

router.get("/system", async (req, res, next) => {
    try {
        await db.execute("SELECT 1");
        return res.json({
            success: true,
            data: {
                backend: "online",
                database: "connected",
                supportedFormats: ["CSV", "XLSX", "XLS"],
                maximumUploadMb: 10,
                modules: [
                    { id: 1, name: "Authentication", status: "completed" },
                    { id: 2, name: "Data Ingestion", status: "completed" },
                    { id: 3, name: "Validation", status: "upcoming" },
                    { id: 4, name: "Transformation", status: "upcoming" },
                    { id: 5, name: "Business Data Storage", status: "upcoming" },
                    { id: 6, name: "Analytics", status: "upcoming" },
                    { id: 7, name: "Dashboard & Drilldown", status: "upcoming" },
                    { id: 8, name: "Reports & Export", status: "upcoming" }
                ]
            }
        });
    } catch (error) { next(error); }
});

module.exports = router;

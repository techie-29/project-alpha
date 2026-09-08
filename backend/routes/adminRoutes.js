const express = require("express");
const db = require("../config/db");

const router = express.Router();

router.get("/dashboard", async (req, res, next) => {
    try {
        const [[accountStats]] = await db.execute(`
            SELECT
                COUNT(*) AS totalAccounts,
                COALESCE(SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END), 0) AS adminAccounts,
                COALESCE(SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END), 0) AS businessAccounts,
                COALESCE(SUM(CASE WHEN account_status = 'disabled' THEN 1 ELSE 0 END), 0) AS disabledAccounts
            FROM business_accounts
        `);

        const [[ingestionStats]] = await db.execute(`
            SELECT
                COUNT(*) AS totalUploads,
                COALESCE(SUM(row_count), 0) AS metadataRows,
                COALESCE(SUM(column_count), 0) AS totalColumns
            FROM ingestions
        `);

        const [[storedRowStats]] = await db.execute(`SELECT COUNT(*) AS totalRows FROM ingestion_rows`);

        const [recentUploads] = await db.execute(`
            SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat,
                   i.row_count AS rowCount, i.column_count AS columnCount, i.status,
                   i.created_at AS createdAt,
                   COALESCE(b.business_name, 'Unknown business') AS businessName, b.email
            FROM ingestions i
            LEFT JOIN business_accounts b ON b.id = i.business_account_id
            ORDER BY i.created_at DESC
            LIMIT 8
        `);

        return res.json({
            success: true,
            data: {
                stats: { ...accountStats, ...ingestionStats, totalRows: storedRowStats.totalRows },
                recentUploads
            }
        });
    } catch (error) { next(error); }
});

router.get("/users", async (req, res, next) => {
    try {
        const [users] = await db.execute(`
            SELECT b.id, b.business_name AS businessName, b.email, b.role,
                   b.account_status AS accountStatus, b.created_at AS createdAt,
                   COUNT(i.id) AS uploadCount
            FROM business_accounts b
            LEFT JOIN ingestions i ON i.business_account_id = b.id
            GROUP BY b.id, b.business_name, b.email, b.role, b.account_status, b.created_at
            ORDER BY b.created_at DESC
        `);
        return res.json({ success: true, data: { users } });
    } catch (error) { next(error); }
});

router.patch("/users/:id/status", async (req, res, next) => {
    try {
        const accountId = Number(req.params.id);
        const status = req.body.status;

        if (!Number.isInteger(accountId) || !["active", "disabled"].includes(status)) {
            return res.status(400).json({ success: false, message: "Valid account id and status are required" });
        }
        if (accountId === req.user.id && status === "disabled") {
            return res.status(400).json({ success: false, message: "You cannot disable your own admin account" });
        }

        const [result] = await db.execute(
            "UPDATE business_accounts SET account_status = ? WHERE id = ?",
            [status, accountId]
        );
        if (result.affectedRows === 0) return res.status(404).json({ success: false, message: "Account not found" });

        return res.json({ success: true, message: `Account ${status}`, data: { accountId, status } });
    } catch (error) { next(error); }
});

router.get("/users/:id/datasets", async (req, res, next) => {
    try {
        const [datasets] = await db.execute(`
            SELECT id, original_file_name AS fileName, file_format AS fileFormat,
                   row_count AS rowCount, column_count AS columnCount, status,
                   created_at AS createdAt
            FROM ingestions
            WHERE business_account_id = ?
            ORDER BY created_at DESC
        `, [req.params.id]);
        return res.json({ success: true, data: { datasets } });
    } catch (error) { next(error); }
});

router.delete("/users/:id", async (req, res, next) => {
    try {
        const accountId = Number(req.params.id);
        if (!Number.isInteger(accountId)) return res.status(400).json({ success: false, message: "Invalid account id" });
        if (accountId === req.user.id) return res.status(400).json({ success: false, message: "You cannot delete your own admin account" });

        const [result] = await db.execute("DELETE FROM business_accounts WHERE id = ?", [accountId]);
        if (result.affectedRows === 0) return res.status(404).json({ success: false, message: "Account not found" });

        return res.json({ success: true, message: "Business account and its related ingestions were deleted" });
    } catch (error) { next(error); }
});

router.get("/datasets", async (req, res, next) => {
    try {
        const [datasets] = await db.execute(`
            SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat,
                   i.file_size_bytes AS fileSizeBytes, i.sheet_name AS sheetName,
                   i.row_count AS rowCount, i.column_count AS columnCount,
                   i.status, i.created_at AS createdAt,
                   COALESCE(b.business_name, 'Unknown business') AS businessName, b.email
            FROM ingestions i
            LEFT JOIN business_accounts b ON b.id = i.business_account_id
            ORDER BY i.created_at DESC
        `);
        return res.json({ success: true, data: { datasets } });
    } catch (error) { next(error); }
});

router.get("/datasets/:id", async (req, res, next) => {
    try {
        const [[dataset]] = await db.execute(`
            SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat,
                   i.file_size_bytes AS fileSizeBytes, i.sheet_name AS sheetName,
                   i.row_count AS rowCount, i.column_count AS columnCount,
                   i.headers_json AS headers, i.profile_json AS profile, i.status,
                   i.created_at AS createdAt, b.business_name AS businessName, b.email
            FROM ingestions i
            LEFT JOIN business_accounts b ON b.id = i.business_account_id
            WHERE i.id = ?
        `, [req.params.id]);
        if (!dataset) return res.status(404).json({ success: false, message: "Dataset not found" });

        const [rows] = await db.execute(`
            SELECT source_row_number AS rowNumber, raw_data AS rawData
            FROM ingestion_rows
            WHERE ingestion_id = ?
            ORDER BY source_row_number ASC
            LIMIT 25
        `, [req.params.id]);

        return res.json({ success: true, data: { dataset, previewRows: rows } });
    } catch (error) { next(error); }
});

router.delete("/datasets/:id", async (req, res, next) => {
    try {
        const [result] = await db.execute("DELETE FROM ingestions WHERE id = ?", [req.params.id]);
        if (result.affectedRows === 0) return res.status(404).json({ success: false, message: "Dataset not found" });
        return res.json({ success: true, message: "Dataset and its stored ingestion rows were deleted" });
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

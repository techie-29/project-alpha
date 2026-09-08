const express = require("express");
const db = require("../config/db");

const router = express.Router();

async function writeAudit(executor, adminId, action, targetType, targetId, details = {}) {
    await executor.execute(
        `INSERT INTO admin_activity_logs
         (admin_account_id, action, target_type, target_id, details_json)
         VALUES (?, ?, ?, ?, ?)`,
        [adminId, action, targetType, targetId, JSON.stringify(details)]
    );
}

router.get("/dashboard", async (req, res, next) => {
    try {
        const [[accountStats]] = await db.execute(`
            SELECT COUNT(*) AS totalAccounts,
                   COALESCE(SUM(role = 'admin'), 0) AS adminAccounts,
                   COALESCE(SUM(role = 'user'), 0) AS businessAccounts,
                   COALESCE(SUM(account_status = 'disabled'), 0) AS disabledAccounts
            FROM business_accounts
        `);
        const [[ingestionStats]] = await db.execute(`
            SELECT COUNT(*) AS totalUploads,
                   COALESCE(SUM(row_count), 0) AS metadataRows,
                   COALESCE(SUM(column_count), 0) AS totalColumns
            FROM ingestions
        `);
        const [[storedRowStats]] = await db.execute("SELECT COUNT(*) AS totalRows FROM ingestion_rows");
        const [recentUploads] = await db.execute(`
            SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat,
                   i.row_count AS rowCount, i.column_count AS columnCount, i.status,
                   i.created_at AS createdAt,
                   COALESCE(b.business_name, 'Unknown business') AS businessName, b.email
            FROM ingestions i
            LEFT JOIN business_accounts b ON b.id = i.business_account_id
            ORDER BY i.created_at DESC LIMIT 8
        `);
        return res.json({ success: true, data: { stats: { ...accountStats, ...ingestionStats, totalRows: storedRowStats.totalRows }, recentUploads } });
    } catch (error) { next(error); }
});

router.get("/activity", async (req, res, next) => {
    try {
        const [activity] = await db.execute(`
            SELECT l.id, l.action, l.target_type AS targetType, l.target_id AS targetId,
                   l.details_json AS details, l.created_at AS createdAt,
                   COALESCE(b.business_name, b.email, 'Deleted administrator') AS adminName
            FROM admin_activity_logs l
            LEFT JOIN business_accounts b ON b.id = l.admin_account_id
            ORDER BY l.created_at DESC
            LIMIT 100
        `);
        return res.json({ success: true, data: { activity } });
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
    const accountId = Number(req.params.id);
    const status = req.body.status;
    if (!Number.isInteger(accountId) || !["active", "disabled"].includes(status)) return res.status(400).json({ success: false, message: "Valid account id and status are required" });
    if (accountId === req.user.id && status === "disabled") return res.status(400).json({ success: false, message: "You cannot disable your own admin account" });

    const connection = await db.getConnection();
    try {
        await connection.beginTransaction();
        const [[target]] = await connection.execute("SELECT business_name AS businessName, email, role, account_status AS accountStatus FROM business_accounts WHERE id = ? FOR UPDATE", [accountId]);
        if (!target) { await connection.rollback(); return res.status(404).json({ success: false, message: "Account not found" }); }
        if (target.role === "admin") { await connection.rollback(); return res.status(400).json({ success: false, message: "Administrator accounts cannot be changed from business controls" }); }
        await connection.execute("UPDATE business_accounts SET account_status = ? WHERE id = ?", [status, accountId]);
        await writeAudit(connection, req.user.id, status === "disabled" ? "business_disabled" : "business_enabled", "business_account", accountId, { businessName: target.businessName, email: target.email, previousStatus: target.accountStatus, newStatus: status });
        await connection.commit();
        return res.json({ success: true, message: `Account ${status}`, data: { accountId, status } });
    } catch (error) { await connection.rollback(); next(error); }
    finally { connection.release(); }
});

router.get("/users/:id/datasets", async (req, res, next) => {
    try {
        const accountId = Number(req.params.id);
        if (!Number.isInteger(accountId)) return res.status(400).json({ success: false, message: "Invalid account id" });
        const [datasets] = await db.execute(`SELECT id, original_file_name AS fileName, file_format AS fileFormat, row_count AS rowCount, column_count AS columnCount, status, created_at AS createdAt FROM ingestions WHERE business_account_id = ? ORDER BY created_at DESC`, [accountId]);
        return res.json({ success: true, data: { datasets } });
    } catch (error) { next(error); }
});

router.delete("/users/:id", async (req, res, next) => {
    const accountId = Number(req.params.id);
    if (!Number.isInteger(accountId)) return res.status(400).json({ success: false, message: "Invalid account id" });
    if (accountId === req.user.id) return res.status(400).json({ success: false, message: "You cannot delete your own admin account" });

    const connection = await db.getConnection();
    try {
        await connection.beginTransaction();
        const [[target]] = await connection.execute("SELECT business_name AS businessName, email, role FROM business_accounts WHERE id = ? FOR UPDATE", [accountId]);
        if (!target) { await connection.rollback(); return res.status(404).json({ success: false, message: "Account not found" }); }
        if (target.role === "admin") { await connection.rollback(); return res.status(400).json({ success: false, message: "Administrator accounts cannot be deleted from business controls" }); }
        const [[counts]] = await connection.execute(`SELECT COUNT(DISTINCT i.id) AS datasetCount, COUNT(r.id) AS rowCount FROM ingestions i LEFT JOIN ingestion_rows r ON r.ingestion_id = i.id WHERE i.business_account_id = ?`, [accountId]);
        await writeAudit(connection, req.user.id, "business_deleted", "business_account", accountId, { businessName: target.businessName, email: target.email, datasetCount: counts.datasetCount, rowCount: counts.rowCount });
        await connection.execute("DELETE FROM business_accounts WHERE id = ?", [accountId]);
        await connection.commit();
        return res.json({ success: true, message: "Business account and its related ingestions were deleted" });
    } catch (error) { await connection.rollback(); next(error); }
    finally { connection.release(); }
});

router.get("/datasets", async (req, res, next) => {
    try {
        const [datasets] = await db.execute(`SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat, i.file_size_bytes AS fileSizeBytes, i.sheet_name AS sheetName, i.row_count AS rowCount, i.column_count AS columnCount, i.status, i.created_at AS createdAt, COALESCE(b.business_name, 'Unknown business') AS businessName, b.email FROM ingestions i LEFT JOIN business_accounts b ON b.id = i.business_account_id ORDER BY i.created_at DESC`);
        return res.json({ success: true, data: { datasets } });
    } catch (error) { next(error); }
});

router.get("/datasets/:id", async (req, res, next) => {
    try {
        const datasetId = Number(req.params.id);
        if (!Number.isInteger(datasetId)) return res.status(400).json({ success: false, message: "Invalid dataset id" });
        const [[dataset]] = await db.execute(`SELECT i.id, i.original_file_name AS fileName, i.file_format AS fileFormat, i.file_size_bytes AS fileSizeBytes, i.sheet_name AS sheetName, i.row_count AS rowCount, i.column_count AS columnCount, i.headers_json AS headers, i.profile_json AS profile, i.status, i.created_at AS createdAt, b.business_name AS businessName, b.email FROM ingestions i LEFT JOIN business_accounts b ON b.id = i.business_account_id WHERE i.id = ?`, [datasetId]);
        if (!dataset) return res.status(404).json({ success: false, message: "Dataset not found" });
        const [rows] = await db.execute(`SELECT source_row_number AS rowNumber, raw_data AS rawData FROM ingestion_rows WHERE ingestion_id = ? ORDER BY source_row_number ASC LIMIT 25`, [datasetId]);
        return res.json({ success: true, data: { dataset, previewRows: rows } });
    } catch (error) { next(error); }
});

router.delete("/datasets/:id", async (req, res, next) => {
    const datasetId = Number(req.params.id);
    if (!Number.isInteger(datasetId)) return res.status(400).json({ success: false, message: "Invalid dataset id" });
    const connection = await db.getConnection();
    try {
        await connection.beginTransaction();
        const [[dataset]] = await connection.execute(`SELECT i.original_file_name AS fileName, i.row_count AS rowCount, i.business_account_id AS businessAccountId, b.business_name AS businessName FROM ingestions i LEFT JOIN business_accounts b ON b.id = i.business_account_id WHERE i.id = ? FOR UPDATE`, [datasetId]);
        if (!dataset) { await connection.rollback(); return res.status(404).json({ success: false, message: "Dataset not found" }); }
        await writeAudit(connection, req.user.id, "dataset_deleted", "ingestion", datasetId, dataset);
        await connection.execute("DELETE FROM ingestions WHERE id = ?", [datasetId]);
        await connection.commit();
        return res.json({ success: true, message: "Dataset and its stored ingestion rows were deleted" });
    } catch (error) { await connection.rollback(); next(error); }
    finally { connection.release(); }
});

router.get("/system", async (req, res, next) => {
    try {
        await db.execute("SELECT 1");
        return res.json({ success: true, data: { backend: "online", database: "connected", supportedFormats: ["CSV", "XLSX", "XLS"], maximumUploadMb: 10, modules: [
            { id: 1, name: "Authentication", status: "completed" }, { id: 2, name: "Data Ingestion", status: "completed" }, { id: 3, name: "Validation", status: "upcoming" }, { id: 4, name: "Transformation", status: "upcoming" }, { id: 5, name: "Business Data Storage", status: "upcoming" }, { id: 6, name: "Analytics", status: "upcoming" }, { id: 7, name: "Dashboard & Drilldown", status: "upcoming" }, { id: 8, name: "Reports & Export", status: "upcoming" }
        ] } });
    } catch (error) { next(error); }
});

module.exports = router;

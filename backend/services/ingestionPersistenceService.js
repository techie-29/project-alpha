const db = require("../config/db");

const ROW_BATCH_SIZE = 250;

async function insertRows(connection, ingestionId, rows) {
    for (let start = 0; start < rows.length; start += ROW_BATCH_SIZE) {
        const batch = rows.slice(start, start + ROW_BATCH_SIZE);
        const placeholders = batch.map(() => "(?, ?, ?)").join(", ");
        const values = [];

        batch.forEach((row, index) => {
            values.push(
                ingestionId,
                start + index + 1,
                JSON.stringify(row)
            );
        });

        await connection.execute(
            `INSERT INTO ingestion_rows (
                ingestion_id,
                source_row_number,
                raw_data
            ) VALUES ${placeholders}`,
            values
        );
    }
}

async function saveIngestion({
    businessAccountId,
    sourceFile,
    dataset,
    profile
}) {
    let connection;

    try {
        connection = await db.getConnection();
        await connection.beginTransaction();

        const [result] = await connection.execute(
            `INSERT INTO ingestions (
                business_account_id,
                original_file_name,
                file_format,
                file_size_bytes,
                sheet_name,
                row_count,
                column_count,
                headers_json,
                profile_json,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
                businessAccountId,
                sourceFile.fileName,
                sourceFile.format,
                sourceFile.sizeBytes,
                sourceFile.sheetName,
                profile.rowCount,
                profile.columnCount,
                JSON.stringify(dataset.headers),
                JSON.stringify(profile),
                "ready_for_validation"
            ]
        );

        await insertRows(connection, result.insertId, dataset.rows);
        await connection.commit();

        return result.insertId;
    } catch (error) {
        if (connection) {
            try {
                await connection.rollback();
            } catch (rollbackError) {
                console.error("Could not roll back ingestion:", rollbackError.message);
            }
        }

        error.status = 500;
        throw error;
    } finally {
        connection?.release();
    }
}

module.exports = {
    saveIngestion
};

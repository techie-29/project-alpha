const db = require("../config/db");

async function createBatch({ businessAccountId, files }) {
  let connection;

  try {
    connection = await db.getConnection();
    await connection.beginTransaction();

    const [batchResult] = await connection.execute(
      `INSERT INTO ingestion_batches (
        business_account_id,
        status,
        total_files,
        completed_files,
        failed_files
      ) VALUES (?, 'processing', ?, 0, 0)`,
      [businessAccountId, files.length]
    );

    const batchId = batchResult.insertId;
    const placeholders = files.map(() => "(?, ?, ?, 'queued')").join(", ");
    const values = [];
    files.forEach((file, index) => {
      values.push(batchId, index, file.originalname);
    });

    await connection.execute(
      `INSERT INTO ingestion_batch_items (
        batch_id,
        file_index,
        original_file_name,
        status
      ) VALUES ${placeholders}`,
      values
    );

    await connection.commit();
    return batchId;
  } catch (error) {
    if (connection) await connection.rollback();
    throw error;
  } finally {
    connection?.release();
  }
}

async function markItemProcessing({ batchId, fileIndex }) {
  await db.execute(
    `UPDATE ingestion_batch_items
     SET status = 'processing', error_code = NULL, error_message = NULL
     WHERE batch_id = ? AND file_index = ?`,
    [batchId, fileIndex]
  );
}

async function recordItemResult({ batchId, fileIndex, ingestionId = null, error = null }) {
  let connection;

  try {
    connection = await db.getConnection();
    await connection.beginTransaction();

    const succeeded = !error;
    await connection.execute(
      `UPDATE ingestion_batch_items
       SET status = ?, ingestion_id = ?, error_code = ?, error_message = ?
       WHERE batch_id = ? AND file_index = ?`,
      [
        succeeded ? "completed" : "failed",
        ingestionId,
        error?.code || null,
        error?.message || null,
        batchId,
        fileIndex
      ]
    );

    await connection.execute(
      `UPDATE ingestion_batches
       SET completed_files = completed_files + ?,
           failed_files = failed_files + ?
       WHERE id = ?`,
      [succeeded ? 1 : 0, succeeded ? 0 : 1, batchId]
    );

    await connection.commit();
  } catch (databaseError) {
    if (connection) await connection.rollback();
    throw databaseError;
  } finally {
    connection?.release();
  }
}

async function finishBatch(batchId) {
  const [rows] = await db.execute(
    `SELECT total_files, completed_files, failed_files
     FROM ingestion_batches
     WHERE id = ?
     LIMIT 1`,
    [batchId]
  );

  if (!rows[0]) throw new Error("Upload batch no longer exists");

  const batch = rows[0];
  const status = batch.completed_files === batch.total_files
    ? "completed"
    : batch.failed_files === batch.total_files
      ? "failed"
      : "partial";

  await db.execute(
    `UPDATE ingestion_batches
     SET status = ?, completed_at = CURRENT_TIMESTAMP
     WHERE id = ?`,
    [status, batchId]
  );

  return {
    id: batchId,
    status,
    totalFiles: batch.total_files,
    completedFiles: batch.completed_files,
    failedFiles: batch.failed_files
  };
}

async function getBatch({ businessAccountId, batchId }) {
  const [batches] = await db.execute(
    `SELECT id, status, total_files, completed_files, failed_files,
            created_at, completed_at
     FROM ingestion_batches
     WHERE id = ? AND business_account_id = ?
     LIMIT 1`,
    [batchId, businessAccountId]
  );

  if (!batches[0]) return null;

  const [items] = await db.execute(
    `SELECT file_index, original_file_name, status, ingestion_id,
            error_code, error_message, updated_at
     FROM ingestion_batch_items
     WHERE batch_id = ?
     ORDER BY file_index`,
    [batchId]
  );

  const batch = batches[0];
  return {
    id: batch.id,
    status: batch.status,
    totalFiles: batch.total_files,
    completedFiles: batch.completed_files,
    failedFiles: batch.failed_files,
    createdAt: batch.created_at,
    completedAt: batch.completed_at,
    items: items.map((item) => ({
      fileIndex: item.file_index,
      fileName: item.original_file_name,
      status: item.status,
      ingestionId: item.ingestion_id,
      errorCode: item.error_code,
      errorMessage: item.error_message,
      updatedAt: item.updated_at
    }))
  };
}

module.exports = {
  createBatch,
  markItemProcessing,
  recordItemResult,
  finishBatch,
  getBatch
};

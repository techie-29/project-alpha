const db = require("../../config/db");

const json = (v) => (v == null ? null : JSON.stringify(v));
const parse = (v) => (typeof v === "string" ? JSON.parse(v) : v);

async function addFile({ businessAccountId, originalName, storedPath, sizeBytes }) {
  const [r] = await db.execute(
    "INSERT INTO alpha_files (business_account_id, original_name, stored_path, size_bytes) VALUES (?,?,?,?)",
    [businessAccountId, originalName, storedPath, sizeBytes]);
  return { id: r.insertId, name: originalName, sizeBytes };
}
async function listFiles(businessAccountId) {
  const [rows] = await db.execute(
    "SELECT id, original_name AS name, size_bytes AS sizeBytes, created_at AS createdAt FROM alpha_files WHERE business_account_id=? ORDER BY id DESC", [businessAccountId]);
  return rows;
}
async function getFiles(businessAccountId, ids) {
  if (!ids.length) return [];
  const [rows] = await db.query(
    "SELECT id, original_name AS name, stored_path AS path FROM alpha_files WHERE business_account_id=? AND id IN (?)", [businessAccountId, ids]);
  return rows;
}
async function deleteFile(businessAccountId, id) {
  const [rows] = await db.execute("SELECT stored_path AS path FROM alpha_files WHERE id=? AND business_account_id=?", [id, businessAccountId]);
  if (!rows.length) return null;
  await db.execute("DELETE FROM alpha_files WHERE id=? AND business_account_id=?", [id, businessAccountId]);
  return rows[0];
}
async function createAnalysis({ id, businessAccountId, fileIds, confirmations }) {
  await db.execute("INSERT INTO alpha_analyses (id, business_account_id, file_ids, confirmations) VALUES (?,?,?,?)",
    [id, businessAccountId, json(fileIds), json(confirmations || {})]);
}
async function getAnalysis(businessAccountId, id) {
  const [rows] = await db.execute(
    "SELECT id, status, stage, progress, error, file_ids, confirmations, created_at AS createdAt, finished_at AS finishedAt FROM alpha_analyses WHERE id=? AND business_account_id=?", [id, businessAccountId]);
  if (!rows.length) return null;
  const r = rows[0];
  return { ...r, file_ids: parse(r.file_ids), confirmations: parse(r.confirmations) };
}
async function listAnalyses(businessAccountId) {
  const [rows] = await db.execute(
    "SELECT id, status, progress, error, file_ids, created_at AS createdAt, finished_at AS finishedAt FROM alpha_analyses WHERE business_account_id=? ORDER BY created_at DESC LIMIT 50", [businessAccountId]);
  return rows.map((r) => ({ ...r, file_ids: parse(r.file_ids) }));
}
async function updateAnalysis(businessAccountId, id, patch) {
  const map = { status: "status", stage: "stage", progress: "progress", error: "error" };
  const sets = [], vals = [];
  for (const [k, col] of Object.entries(map)) if (k in patch) { sets.push(`${col}=?`); vals.push(patch[k]); }
  if ("report" in patch) { sets.push("report=?"); vals.push(JSON.stringify(patch.report)); }
  if (patch.status === "done" || patch.status === "failed") sets.push("finished_at=CURRENT_TIMESTAMP");
  if (!sets.length) return;
  await db.execute(`UPDATE alpha_analyses SET ${sets.join(",")} WHERE id=? AND business_account_id=?`, [...vals, id, businessAccountId]);
}
async function getReport(businessAccountId, id) {
  const [rows] = await db.execute("SELECT report FROM alpha_analyses WHERE id=? AND business_account_id=? AND status='done'", [id, businessAccountId]);
  return rows.length && rows[0].report ? parse(rows[0].report) : null;
}
async function saveFeedback({ businessAccountId, analysisId, findingId, patternKey, verdict, note }) {
  await db.execute(
    `INSERT INTO alpha_feedback (business_account_id, analysis_id, finding_id, pattern_key, verdict, note) VALUES (?,?,?,?,?,?)
     ON DUPLICATE KEY UPDATE verdict=VALUES(verdict), note=VALUES(note), pattern_key=VALUES(pattern_key)`, [businessAccountId, analysisId, findingId, patternKey || null, verdict, note || null]);
}
/** Latest verdict per kind of finding, across all of this account's analyses. */
async function listPatternPreferences(businessAccountId) {
  const [rows] = await db.execute(
    "SELECT pattern_key AS patternKey, verdict FROM alpha_feedback WHERE business_account_id=? AND pattern_key IS NOT NULL ORDER BY id ASC", [businessAccountId]);
  return rows;
}
async function listFeedback(businessAccountId, analysisId) {
  const [rows] = await db.execute("SELECT finding_id AS findingId, verdict, note FROM alpha_feedback WHERE business_account_id=? AND analysis_id=?", [businessAccountId, analysisId]);
  return rows;
}
async function saveAnswer({ businessAccountId, analysisId, questionId, answer }) {
  await db.execute(
    `INSERT INTO alpha_answers (business_account_id, analysis_id, question_id, answer) VALUES (?,?,?,?)
     ON DUPLICATE KEY UPDATE answer=VALUES(answer)`, [businessAccountId, analysisId, questionId, answer]);
}
async function listAnswers(businessAccountId, analysisId) {
  const [rows] = await db.execute("SELECT question_id AS questionId, answer FROM alpha_answers WHERE business_account_id=? AND analysis_id=?", [businessAccountId, analysisId]);
  return rows;
}

async function listMemory(businessAccountId) {
  const [rows] = await db.execute("SELECT column_key AS columnKey, concept FROM alpha_memory WHERE business_account_id=?", [businessAccountId]);
  return Object.fromEntries(rows.map((r) => [r.columnKey, r.concept]));
}
async function saveMemory(businessAccountId, entries) {
  for (const [columnKey, concept] of entries) {
    await db.execute(
      `INSERT INTO alpha_memory (business_account_id, column_key, concept) VALUES (?,?,?)
       ON DUPLICATE KEY UPDATE concept=VALUES(concept)`, [businessAccountId, columnKey, concept]);
  }
}
async function saveQuestion({ businessAccountId, analysisId, question, result }) {
  await db.execute("INSERT INTO alpha_questions (business_account_id, analysis_id, question, result) VALUES (?,?,?,?)",
    [businessAccountId, analysisId, question, JSON.stringify(result)]);
}
async function listQuestions(businessAccountId, analysisId) {
  const [rows] = await db.execute(
    "SELECT question, result, created_at AS createdAt FROM alpha_questions WHERE business_account_id=? AND analysis_id=? ORDER BY id ASC LIMIT 100", [businessAccountId, analysisId]);
  return rows.map((r) => ({ question: r.question, result: parse(r.result), createdAt: r.createdAt }));
}

module.exports = { listMemory, saveMemory, saveQuestion, listQuestions,  addFile, listFiles, getFiles, deleteFile, createAnalysis, getAnalysis, listAnalyses, updateAnalysis, getReport, saveFeedback, listPatternPreferences, listFeedback, saveAnswer, listAnswers };

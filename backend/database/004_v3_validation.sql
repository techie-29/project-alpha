USE project_alpha;

-- Upgrade legacy ingestion_rows without deleting raw rows. Older Alpha
-- databases used row_number; V3 consistently uses source_row_number.
SET @has_source_row_number = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'source_row_number'
);
SET @has_legacy_row_number = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'row_number'
);
SET @sql = IF(
  @has_source_row_number = 0 AND @has_legacy_row_number = 1,
  'ALTER TABLE ingestion_rows CHANGE COLUMN row_number source_row_number INT UNSIGNED NOT NULL',
  IF(@has_source_row_number = 0,
    'ALTER TABLE ingestion_rows ADD COLUMN source_row_number INT UNSIGNED NOT NULL AFTER ingestion_id',
    'SELECT "source_row_number already exists"')
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_validation_status = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'validation_status'
);
SET @sql = IF(@has_validation_status = 0,
  'ALTER TABLE ingestion_rows ADD COLUMN validation_status VARCHAR(20) NOT NULL DEFAULT "pending" AFTER raw_data',
  'SELECT "validation_status already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_validation_issues = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'validation_issues'
);
SET @sql = IF(@has_validation_issues = 0,
  'ALTER TABLE ingestion_rows ADD COLUMN validation_issues JSON NULL AFTER validation_status',
  'SELECT "validation_issues already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_transformed_data = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'transformed_data'
);
SET @sql = IF(@has_transformed_data = 0,
  'ALTER TABLE ingestion_rows ADD COLUMN transformed_data JSON NULL AFTER validation_issues',
  'SELECT "transformed_data already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ingestion_rows_created_at = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'created_at'
);
SET @sql = IF(@has_ingestion_rows_created_at = 0,
  'ALTER TABLE ingestion_rows ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER transformed_data',
  'SELECT "ingestion_rows.created_at already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_ingestion_rows_updated_at = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestion_rows' AND COLUMN_NAME = 'updated_at'
);
SET @sql = IF(@has_ingestion_rows_updated_at = 0,
  'ALTER TABLE ingestion_rows ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at',
  'SELECT "ingestion_rows.updated_at already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_validation_summary = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ingestions'
    AND COLUMN_NAME = 'validation_summary_json'
);
SET @sql = IF(
  @has_validation_summary = 0,
  'ALTER TABLE ingestions ADD COLUMN validation_summary_json JSON NULL AFTER profile_json',
  'SELECT "validation_summary_json already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS validation_issues (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ingestion_id INT UNSIGNED NOT NULL,
    business_account_id INT UNSIGNED NOT NULL,
    row_index INT UNSIGNED NOT NULL,
    field_name VARCHAR(100) NULL,
    issue_code VARCHAR(80) NOT NULL,
    severity ENUM('error', 'warning', 'repaired') NOT NULL,
    original_value JSON NULL,
    message VARCHAR(500) NOT NULL,
    action ENUM('skipped', 'repaired', 'kept') NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_validation_issues_ingestion FOREIGN KEY (ingestion_id)
        REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT fk_validation_issues_business FOREIGN KEY (business_account_id)
        REFERENCES business_accounts(id) ON DELETE CASCADE,
    INDEX idx_validation_issues_dataset (business_account_id, ingestion_id),
    INDEX idx_validation_issues_code (ingestion_id, issue_code)
);

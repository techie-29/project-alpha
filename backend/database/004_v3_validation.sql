USE project_alpha;

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

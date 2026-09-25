USE project_alpha;

-- Alpha V3 foundation: add dataset identity and processing metadata
-- Safe to run on the existing Module 1-3 database.

SET @has_file_hash = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ingestions'
    AND COLUMN_NAME = 'file_hash'
);
SET @sql = IF(
  @has_file_hash = 0,
  'ALTER TABLE ingestions ADD COLUMN file_hash CHAR(64) NULL AFTER file_size_bytes',
  'SELECT "file_hash already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_dataset_type = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ingestions'
    AND COLUMN_NAME = 'dataset_type'
);
SET @sql = IF(
  @has_dataset_type = 0,
  'ALTER TABLE ingestions ADD COLUMN dataset_type VARCHAR(40) NULL AFTER file_hash',
  'SELECT "dataset_type already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_included = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ingestions'
    AND COLUMN_NAME = 'included'
);
SET @sql = IF(
  @has_included = 0,
  'ALTER TABLE ingestions ADD COLUMN included BOOLEAN NOT NULL DEFAULT TRUE AFTER dataset_type',
  'SELECT "included already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Existing rows may not have a hash. MySQL unique indexes allow multiple NULL
-- values, so legacy rows coexist while new non-null hashes stay unique.
SET @has_hash_index = (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ingestions'
    AND INDEX_NAME = 'idx_ingestions_business_file_hash'
);
SET @sql = IF(
  @has_hash_index = 0,
  'CREATE UNIQUE INDEX idx_ingestions_business_file_hash ON ingestions (business_account_id, file_hash)',
  'SELECT "idx_ingestions_business_file_hash already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

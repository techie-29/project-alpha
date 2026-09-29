USE project_alpha;

SET @has_currency_code = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'business_accounts' AND COLUMN_NAME = 'currency_code'
);
SET @sql = IF(@has_currency_code = 0,
  'ALTER TABLE business_accounts ADD COLUMN currency_code CHAR(3) NOT NULL DEFAULT "USD" AFTER account_status',
  'SELECT "currency_code already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_timezone = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'business_accounts' AND COLUMN_NAME = 'timezone'
);
SET @sql = IF(@has_timezone = 0,
  'ALTER TABLE business_accounts ADD COLUMN timezone VARCHAR(80) NOT NULL DEFAULT "UTC" AFTER currency_code',
  'SELECT "timezone already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_date_format = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'business_accounts' AND COLUMN_NAME = 'date_format'
);
SET @sql = IF(@has_date_format = 0,
  'ALTER TABLE business_accounts ADD COLUMN date_format VARCHAR(20) NOT NULL DEFAULT "YYYY-MM-DD" AFTER timezone',
  'SELECT "date_format already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

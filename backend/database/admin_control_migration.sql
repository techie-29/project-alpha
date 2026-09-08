USE project_alpha;

-- Safe to run again: add account_status only when it does not already exist.
SET @has_account_status = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'business_accounts'
      AND COLUMN_NAME = 'account_status'
);

SET @add_account_status = IF(
    @has_account_status = 0,
    "ALTER TABLE business_accounts ADD COLUMN account_status ENUM('active','disabled') NOT NULL DEFAULT 'active' AFTER role",
    "SELECT 'account_status already exists'"
);
PREPARE stmt FROM @add_account_status;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Audit history for actions that change the application.
CREATE TABLE IF NOT EXISTS admin_activity_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    admin_account_id INT UNSIGNED NULL,
    action VARCHAR(60) NOT NULL,
    target_type VARCHAR(40) NOT NULL,
    target_id BIGINT UNSIGNED NULL,
    details_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_admin_activity_admin FOREIGN KEY (admin_account_id) REFERENCES business_accounts(id) ON DELETE SET NULL,
    INDEX idx_admin_activity_created_at (created_at),
    INDEX idx_admin_activity_admin (admin_account_id)
);

-- Promote the chosen administrator separately if needed:
-- UPDATE business_accounts
-- SET role = 'admin', account_status = 'active'
-- WHERE email = 'your-admin-email@example.com';

SELECT id, business_name, email, role, account_status
FROM business_accounts;

CREATE DATABASE IF NOT EXISTS project_alpha;
USE project_alpha;

CREATE TABLE IF NOT EXISTS business_accounts (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestions (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    original_file_name VARCHAR(255) NOT NULL,
    file_format VARCHAR(10) NOT NULL,
    file_size_bytes INT UNSIGNED NOT NULL,
    sheet_name VARCHAR(255) NULL,
    row_count INT UNSIGNED NOT NULL,
    column_count INT UNSIGNED NOT NULL,
    headers_json JSON NOT NULL,
    profile_json JSON NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'ready_for_validation',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ingestions_business_account FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    INDEX idx_ingestions_business_account_created_at (business_account_id, created_at)
);

CREATE TABLE IF NOT EXISTS ingestion_rows (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ingestion_id INT UNSIGNED NOT NULL,
    row_number INT UNSIGNED NOT NULL,
    raw_data JSON NOT NULL,
    validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    validation_issues JSON NULL,
    transformed_data JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ingestion_rows_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_ingestion_rows_number UNIQUE (ingestion_id, row_number)
);

-- Existing databases created before the admin panel need this once:
-- ALTER TABLE business_accounts ADD COLUMN role ENUM('user', 'admin') NOT NULL DEFAULT 'user' AFTER password_hash;
-- Promote a chosen existing account manually after the column exists:
-- UPDATE business_accounts SET role = 'admin' WHERE email = 'your-admin-email@example.com';

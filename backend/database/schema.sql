CREATE DATABASE IF NOT EXISTS project_alpha;
USE project_alpha;

CREATE TABLE IF NOT EXISTS business_accounts (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    account_status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestions (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    original_file_name VARCHAR(255) NOT NULL,
    file_format VARCHAR(10) NOT NULL,
    file_size_bytes INT UNSIGNED NOT NULL,
    file_hash CHAR(64) NULL,
    dataset_type VARCHAR(40) NULL,
    included BOOLEAN NOT NULL DEFAULT TRUE,
    sheet_name VARCHAR(255) NULL,
    row_count INT UNSIGNED NOT NULL,
    column_count INT UNSIGNED NOT NULL,
    headers_json JSON NOT NULL,
    profile_json JSON NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'ready_for_validation',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ingestions_business_account FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    INDEX idx_ingestions_business_account_created_at (business_account_id, created_at),
    UNIQUE INDEX idx_ingestions_business_file_hash (business_account_id, file_hash)
);

CREATE TABLE IF NOT EXISTS ingestion_rows (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ingestion_id INT UNSIGNED NOT NULL,
    source_row_number INT UNSIGNED NOT NULL,
    raw_data JSON NOT NULL,
    validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    validation_issues JSON NULL,
    transformed_data JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ingestion_rows_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_ingestion_rows_number UNIQUE (ingestion_id, source_row_number)
);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processing',
    total_files INT UNSIGNED NOT NULL,
    completed_files INT UNSIGNED NOT NULL DEFAULT 0,
    failed_files INT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    CONSTRAINT fk_ingestion_batches_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    INDEX idx_ingestion_batches_business_created (business_account_id, created_at)
);

CREATE TABLE IF NOT EXISTS ingestion_batch_items (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    batch_id BIGINT UNSIGNED NOT NULL,
    file_index INT UNSIGNED NOT NULL,
    original_file_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    ingestion_id INT UNSIGNED NULL,
    error_code VARCHAR(80) NULL,
    error_message VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_batch_items_batch FOREIGN KEY (batch_id) REFERENCES ingestion_batches(id) ON DELETE CASCADE,
    CONSTRAINT fk_batch_items_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE SET NULL,
    CONSTRAINT uq_batch_items_file_index UNIQUE (batch_id, file_index),
    INDEX idx_batch_items_ingestion (ingestion_id)
);

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

-- For existing databases, use database/admin_control_migration.sql.

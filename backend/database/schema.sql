CREATE DATABASE IF NOT EXISTS project_alpha;
USE project_alpha;

CREATE TABLE IF NOT EXISTS business_accounts (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    account_status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    timezone VARCHAR(80) NOT NULL DEFAULT 'UTC',
    date_format VARCHAR(20) NOT NULL DEFAULT 'YYYY-MM-DD',
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
    validation_summary_json JSON NULL,
    transformation_summary_json JSON NULL,
    quality_summary_json JSON NULL,
    date_from DATE NULL,
    date_to DATE NULL,
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

CREATE TABLE IF NOT EXISTS dataset_mappings (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ingestion_id INT UNSIGNED NOT NULL,
    business_account_id INT UNSIGNED NOT NULL,
    mapping_json JSON NOT NULL,
    suggestions_json JSON NULL,
    coverage DECIMAL(5,4) NOT NULL DEFAULT 0,
    header_coverage DECIMAL(5,4) NOT NULL DEFAULT 0,
    missing_critical_fields JSON NULL,
    confirmed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_dataset_mappings_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT fk_dataset_mappings_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT uq_dataset_mappings_ingestion UNIQUE (ingestion_id),
    INDEX idx_dataset_mappings_business (business_account_id, ingestion_id)
);

CREATE TABLE IF NOT EXISTS saved_mappings (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    header_signature CHAR(64) NOT NULL,
    mapping_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_saved_mappings_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT uq_saved_mappings_signature UNIQUE (business_account_id, header_signature)
);

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
    CONSTRAINT fk_validation_issues_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT fk_validation_issues_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    INDEX idx_validation_issues_dataset (business_account_id, ingestion_id),
    INDEX idx_validation_issues_code (ingestion_id, issue_code)
);

CREATE TABLE IF NOT EXISTS sales_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL,
    source_row_number INT UNSIGNED NOT NULL,
    order_id VARCHAR(150) NULL,
    order_date DATE NULL,
    product_key VARCHAR(255) NULL,
    product_name VARCHAR(255) NULL,
    sku VARCHAR(120) NULL,
    category VARCHAR(150) NULL,
    quantity DECIMAL(18,4) NULL,
    unit_price DECIMAL(18,4) NULL,
    discount DECIMAL(18,4) NULL,
    revenue DECIMAL(18,4) NULL,
    cost_price DECIMAL(18,4) NULL,
    profit DECIMAL(18,4) NULL,
    customer_key VARCHAR(255) NULL,
    customer_id VARCHAR(150) NULL,
    customer_name VARCHAR(255) NULL,
    customer_email VARCHAR(255) NULL,
    status VARCHAR(80) NULL,
    notes TEXT NULL,
    repaired_fields JSON NOT NULL,
    computed_fields JSON NOT NULL,
    raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sales_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_sales_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_sales_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_sales_business_date (business_account_id, order_date),
    INDEX idx_sales_business_product (business_account_id, product_key)
);

CREATE TABLE IF NOT EXISTS stock_snapshots (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL,
    source_row_number INT UNSIGNED NOT NULL,
    product_key VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NULL,
    sku VARCHAR(120) NULL,
    stock_qty DECIMAL(18,4) NOT NULL,
    reorder_level DECIMAL(18,4) NULL,
    stock_status VARCHAR(40) NULL,
    stock_as_of_date DATE NULL,
    supplier_name VARCHAR(255) NULL,
    repaired_fields JSON NOT NULL,
    computed_fields JSON NOT NULL,
    raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_stock_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_stock_business_product (business_account_id, product_key),
    INDEX idx_stock_business_date (business_account_id, stock_as_of_date)
);

CREATE TABLE IF NOT EXISTS customer_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL,
    source_row_number INT UNSIGNED NOT NULL,
    customer_key VARCHAR(255) NOT NULL,
    customer_id VARCHAR(150) NULL,
    customer_name VARCHAR(255) NULL,
    customer_email VARCHAR(255) NULL,
    customer_phone VARCHAR(80) NULL,
    region VARCHAR(150) NULL,
    repaired_fields JSON NOT NULL,
    raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_customer_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_customer_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_customer_records_key (business_account_id, customer_key)
);

CREATE TABLE IF NOT EXISTS product_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL,
    source_row_number INT UNSIGNED NOT NULL,
    product_key VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NULL,
    sku VARCHAR(120) NULL,
    category VARCHAR(150) NULL,
    unit_price DECIMAL(18,4) NULL,
    cost_price DECIMAL(18,4) NULL,
    supplier_name VARCHAR(255) NULL,
    repaired_fields JSON NOT NULL,
    raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_product_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_product_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_product_records_key (business_account_id, product_key)
);

CREATE TABLE IF NOT EXISTS supplier_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL,
    source_row_number INT UNSIGNED NOT NULL,
    supplier_key VARCHAR(255) NOT NULL,
    supplier_name VARCHAR(255) NOT NULL,
    repaired_fields JSON NOT NULL,
    raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_supplier_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_supplier_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_supplier_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_supplier_records_key (business_account_id, supplier_key)
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

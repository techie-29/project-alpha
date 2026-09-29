USE project_alpha;

SET @has_transform_summary = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestions' AND COLUMN_NAME = 'transformation_summary_json');
SET @sql = IF(@has_transform_summary = 0, 'ALTER TABLE ingestions ADD COLUMN transformation_summary_json JSON NULL AFTER validation_summary_json', 'SELECT "transformation_summary_json already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_quality_summary = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestions' AND COLUMN_NAME = 'quality_summary_json');
SET @sql = IF(@has_quality_summary = 0, 'ALTER TABLE ingestions ADD COLUMN quality_summary_json JSON NULL AFTER transformation_summary_json', 'SELECT "quality_summary_json already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_date_from = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestions' AND COLUMN_NAME = 'date_from');
SET @sql = IF(@has_date_from = 0, 'ALTER TABLE ingestions ADD COLUMN date_from DATE NULL AFTER quality_summary_json', 'SELECT "date_from already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_date_to = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ingestions' AND COLUMN_NAME = 'date_to');
SET @sql = IF(@has_date_to = 0, 'ALTER TABLE ingestions ADD COLUMN date_to DATE NULL AFTER date_from', 'SELECT "date_to already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS sales_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL, source_row_number INT UNSIGNED NOT NULL,
    order_id VARCHAR(150) NULL, order_date DATE NULL, product_key VARCHAR(255) NULL,
    product_name VARCHAR(255) NULL, sku VARCHAR(120) NULL, category VARCHAR(150) NULL,
    quantity DECIMAL(18,4) NULL, unit_price DECIMAL(18,4) NULL, discount DECIMAL(18,4) NULL,
    revenue DECIMAL(18,4) NULL, cost_price DECIMAL(18,4) NULL, profit DECIMAL(18,4) NULL,
    customer_key VARCHAR(255) NULL, customer_id VARCHAR(150) NULL, customer_name VARCHAR(255) NULL,
    customer_email VARCHAR(255) NULL, status VARCHAR(80) NULL, notes TEXT NULL,
    repaired_fields JSON NOT NULL, computed_fields JSON NOT NULL, raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sales_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_sales_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_sales_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_sales_business_date (business_account_id, order_date),
    INDEX idx_sales_business_product (business_account_id, product_key)
);

CREATE TABLE IF NOT EXISTS stock_snapshots (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL, source_row_number INT UNSIGNED NOT NULL,
    product_key VARCHAR(255) NOT NULL, product_name VARCHAR(255) NULL, sku VARCHAR(120) NULL,
    stock_qty DECIMAL(18,4) NOT NULL, reorder_level DECIMAL(18,4) NULL,
    stock_status VARCHAR(40) NULL, stock_as_of_date DATE NULL, supplier_name VARCHAR(255) NULL,
    repaired_fields JSON NOT NULL, computed_fields JSON NOT NULL, raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_stock_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_stock_business_product (business_account_id, product_key),
    INDEX idx_stock_business_date (business_account_id, stock_as_of_date)
);

CREATE TABLE IF NOT EXISTS customer_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL, source_row_number INT UNSIGNED NOT NULL,
    customer_key VARCHAR(255) NOT NULL, customer_id VARCHAR(150) NULL,
    customer_name VARCHAR(255) NULL, customer_email VARCHAR(255) NULL,
    customer_phone VARCHAR(80) NULL, region VARCHAR(150) NULL,
    repaired_fields JSON NOT NULL, raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_customer_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_customer_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_customer_records_key (business_account_id, customer_key)
);

CREATE TABLE IF NOT EXISTS product_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL, source_row_number INT UNSIGNED NOT NULL,
    product_key VARCHAR(255) NOT NULL, product_name VARCHAR(255) NULL, sku VARCHAR(120) NULL,
    category VARCHAR(150) NULL, unit_price DECIMAL(18,4) NULL, cost_price DECIMAL(18,4) NULL,
    supplier_name VARCHAR(255) NULL, repaired_fields JSON NOT NULL, raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_product_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_product_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_product_records_key (business_account_id, product_key)
);

CREATE TABLE IF NOT EXISTS supplier_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, business_account_id INT UNSIGNED NOT NULL,
    ingestion_id INT UNSIGNED NOT NULL, source_row_number INT UNSIGNED NOT NULL,
    supplier_key VARCHAR(255) NOT NULL, supplier_name VARCHAR(255) NOT NULL,
    repaired_fields JSON NOT NULL, raw_values JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_supplier_records_business FOREIGN KEY (business_account_id) REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_supplier_records_ingestion FOREIGN KEY (ingestion_id) REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT uq_supplier_records_source UNIQUE (ingestion_id, source_row_number),
    INDEX idx_supplier_records_key (business_account_id, supplier_key)
);

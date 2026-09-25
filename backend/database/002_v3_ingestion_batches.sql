USE project_alpha;

-- Persistent progress for multi-file uploads. Each file keeps its own state
-- and may fail without rolling back successful files in the same batch.

CREATE TABLE IF NOT EXISTS ingestion_batches (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    business_account_id INT UNSIGNED NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processing',
    total_files INT UNSIGNED NOT NULL,
    completed_files INT UNSIGNED NOT NULL DEFAULT 0,
    failed_files INT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    CONSTRAINT fk_ingestion_batches_business FOREIGN KEY (business_account_id)
        REFERENCES business_accounts(id) ON DELETE CASCADE,
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
    CONSTRAINT fk_batch_items_batch FOREIGN KEY (batch_id)
        REFERENCES ingestion_batches(id) ON DELETE CASCADE,
    CONSTRAINT fk_batch_items_ingestion FOREIGN KEY (ingestion_id)
        REFERENCES ingestions(id) ON DELETE SET NULL,
    CONSTRAINT uq_batch_items_file_index UNIQUE (batch_id, file_index),
    INDEX idx_batch_items_ingestion (ingestion_id)
);

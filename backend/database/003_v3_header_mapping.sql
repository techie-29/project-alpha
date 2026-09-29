USE project_alpha;

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
    CONSTRAINT fk_dataset_mappings_ingestion FOREIGN KEY (ingestion_id)
        REFERENCES ingestions(id) ON DELETE CASCADE,
    CONSTRAINT fk_dataset_mappings_business FOREIGN KEY (business_account_id)
        REFERENCES business_accounts(id) ON DELETE CASCADE,
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
    CONSTRAINT fk_saved_mappings_business FOREIGN KEY (business_account_id)
        REFERENCES business_accounts(id) ON DELETE CASCADE,
    CONSTRAINT uq_saved_mappings_signature UNIQUE (business_account_id, header_signature)
);

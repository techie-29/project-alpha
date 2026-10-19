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

-- Alpha tables (files, analyses, owner feedback and answers)

CREATE TABLE IF NOT EXISTS alpha_files (
  id INT AUTO_INCREMENT PRIMARY KEY,
  business_account_id INT NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  stored_path VARCHAR(512) NOT NULL,
  size_bytes BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_alpha_files_account (business_account_id)
);

CREATE TABLE IF NOT EXISTS alpha_analyses (
  id CHAR(36) PRIMARY KEY,
  business_account_id INT NOT NULL,
  file_ids JSON NOT NULL,
  confirmations JSON NULL,
  status ENUM('queued','running','done','failed') NOT NULL DEFAULT 'queued',
  stage VARCHAR(160) NOT NULL DEFAULT '',
  progress TINYINT UNSIGNED NOT NULL DEFAULT 0,
  error VARCHAR(500) NULL,
  report LONGTEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP NULL,
  INDEX idx_alpha_analyses_account (business_account_id, created_at)
);

CREATE TABLE IF NOT EXISTS alpha_feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,
  business_account_id INT NOT NULL,
  analysis_id CHAR(36) NOT NULL,
  finding_id VARCHAR(80) NOT NULL,
  pattern_key VARCHAR(200) NULL,
  verdict ENUM('useful','not_useful') NOT NULL,
  note VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_alpha_feedback (business_account_id, analysis_id, finding_id)
);

CREATE TABLE IF NOT EXISTS alpha_answers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  business_account_id INT NOT NULL,
  analysis_id CHAR(36) NOT NULL,
  question_id VARCHAR(80) NOT NULL,
  answer VARCHAR(1000) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_alpha_answers (business_account_id, analysis_id, question_id)
);

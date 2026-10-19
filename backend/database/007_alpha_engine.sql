USE project_alpha;

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

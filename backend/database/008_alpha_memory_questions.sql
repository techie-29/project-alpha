USE project_alpha;

-- What each business confirmed a column means (by normalised column name), reused on its next uploads
CREATE TABLE IF NOT EXISTS alpha_memory (
  id INT AUTO_INCREMENT PRIMARY KEY,
  business_account_id INT NOT NULL,
  column_key VARCHAR(200) NOT NULL,
  concept VARCHAR(60) NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_alpha_memory (business_account_id, column_key)
);

-- Ask Alpha questions and answers, per analysis
CREATE TABLE IF NOT EXISTS alpha_questions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  business_account_id INT NOT NULL,
  analysis_id CHAR(36) NOT NULL,
  question VARCHAR(500) NOT NULL,
  result LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_alpha_questions (business_account_id, analysis_id, created_at)
);

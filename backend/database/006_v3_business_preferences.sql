USE project_alpha;

ALTER TABLE business_accounts
    ADD COLUMN currency_code CHAR(3) NOT NULL DEFAULT 'USD' AFTER account_status,
    ADD COLUMN timezone VARCHAR(80) NOT NULL DEFAULT 'UTC' AFTER currency_code,
    ADD COLUMN date_format VARCHAR(20) NOT NULL DEFAULT 'YYYY-MM-DD' AFTER timezone;

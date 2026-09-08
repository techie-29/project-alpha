USE project_alpha;

-- Run this once on an existing Project Alpha database before testing
-- the new admin-control branch.

ALTER TABLE business_accounts
ADD COLUMN account_status ENUM('active', 'disabled') NOT NULL DEFAULT 'active' AFTER role;

-- Make sure the administrator itself remains usable.
-- Replace the email below with the account you already promoted to admin.
-- UPDATE business_accounts
-- SET role = 'admin', account_status = 'active'
-- WHERE email = 'your-admin-email@example.com';

SELECT id, business_name, email, role, account_status
FROM business_accounts;

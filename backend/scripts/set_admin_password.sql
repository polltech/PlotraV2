-- Reset admin password to 'AdminPass123!'
-- BCrypt hash: $2b$12$r2y4kl6I/qTBUbm4UvpnCOg2f.yOyGoYAKSWbC4X2sA2YNphKphUS

UPDATE users 
SET 
    password_hash = '$2b$12$r2y4kl6I/qTBUbm4UvpnCOg2f.yOyGoYAKSWbC4X2sA2YNphKphUS',
    failed_login_attempts = 0,
    is_locked = false,
    updated_at = NOW()
WHERE email IN ('admin@plotra.com', 'admin@plotra.africa');

-- Verify
SELECT email, phone, LEFT(password_hash, 30) AS hash_prefix, failed_login_attempts 
FROM users 
WHERE email LIKE '%admin%';

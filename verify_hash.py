from passlib.hash import bcrypt

# Test if the hash we stored matches "AdminPass123!"
hash_in_db = '$2b$12$r2y4kl6I/qTBUbm4UvpnCOg2f.yOyGoYAKSWbC4X2sA2YNphKphUS'
password = 'AdminPass123!'

if bcrypt.verify(password, hash_in_db):
    print(f'✓ Hash matches password: "{password}"')
else:
    print(f'✗ Hash does NOT match password: "{password}"')
    
# Also test the alternative password
test_pass = 'AdminPass123'
if bcrypt.verify(test_pass, hash_in_db):
    print(f'✓ Hash matches alternative: "{test_pass}"')
else:
    print(f'✗ Hash does NOT match alternative: "{test_pass}"')

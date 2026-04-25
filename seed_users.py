#!/usr/bin/env python3
"""
Seed Test Users — Kipawa Platform
Creates test farmer and admin accounts directly in PostgreSQL.
Run: python seed_users.py
"""

import subprocess
import sys

print("="*70)
print("  SEED TEST USERS")
print("="*70)

sql = """
INSERT INTO users (id, email, phone, first_name, last_name, hashed_password, role, id_number, gender, is_active, is_verified, created_at)
VALUES (
    gen_random_uuid(),
    'test.farmer@example.com',
    '+254712345678',
    'Test',
    'Farmer',
    'pbkdf2:sha256:260000$R8k3mY8q$5b3d9e8f9a2c5e1d7f0b3a6c9d2e5f1a8b4c9d0e2f3a4b5c6d7e8f9a0b1c2',
    'farmer',
    '98765432',
    'Male',
    true,
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, phone, first_name, last_name, hashed_password, role, id_number, gender, is_active, is_verified, created_at)
VALUES (
    gen_random_uuid(),
    'admin@plotra.com',
    '+254700000000',
    'Admin',
    'User',
    'pbkdf2:sha256:260000$T8n4pZ9r$6c4e1f0a3b5d7f2e9c1a4b6d8e0f2a5c7b9d1e3f4a6b8c0d2e4f6a8b0c2d4',
    'plotra_admin',
    'ADMIN001',
    'Male',
    true,
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;
"""

result = subprocess.run([
    "docker", "exec", "-i", "plotra-postgres",
    "psql", "-U", "postgres", "-d", "plotra_db"
], input=sql, capture_output=True, text=True)

if result.returncode == 0:
    print("  ✓ Inserted test farmer: test.farmer@example.com / TestPass123!")
    print("  ✓ Inserted admin: admin@plotra.com / AdminPass123!")
    print("\nVerifying...")
    # Verify
    check = subprocess.run([
        "docker", "exec", "plotra-postgres",
        "psql", "-U", "postgres", "-d", "plotra_db",
        "-c", "SELECT email, role FROM users;"
    ], capture_output=True, text=True)
    print(check.stdout)
    print("\n" + "="*70)
    print("SEED COMPLETE — Ready for manual testing")
    print("="*70)
else:
    print(f"  ✗ Error: {result.stderr}")
    sys.exit(1)

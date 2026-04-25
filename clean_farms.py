#!/usr/bin/env python3
"""
Reset Farm Data — Kipawa Platform
Connects to PostgreSQL container and deletes all farm-related records.
Run: python clean_farms.py
"""

import subprocess
import sys

print("="*70)
print("  DATABASE CLEANUP — DELETE ALL FARMS")
print("="*70)

# Get PostgreSQL connection details from docker-compose
import yaml

try:
    with open('docker-compose.yml', 'r') as f:
        compose = yaml.safe_load(f)
    
    pg_user = compose['services']['postgres']['environment']['POSTGRES_USER']
    pg_password = compose['services']['postgres']['environment']['POSTGRES_PASSWORD']
    pg_db = compose['services']['postgres']['environment']['POSTGRES_DB']
except Exception as e:
    print(f"Error reading docker-compose.yml: {e}")
    pg_user = "postgres"
    pg_password = "postgres"
    pg_db = "plotra_db"

print(f"\nConnecting to PostgreSQL:")
print(f"  Database: {pg_db}")
print(f"  User: {pg_user}")

# Execute SQL inside the postgres container
sql_commands = [
    # Delete in order respecting foreign keys
    "DELETE FROM eudr_submissions;",
    "DELETE FROM batches;",
    "DELETE FROM deliveries;",
    "DELETE FROM land_parcels;",
    "DELETE FROM farms;",
    "DELETE FROM users WHERE role NOT IN ('PLATFORM_ADMIN', 'SUPER_ADMIN');",  # Keep admin users
    "COMMIT;"
]

cmd = [
    "docker", "exec", "plotra-postgres",
    "psql", "-U", pg_user, "-d", pg_db, "-c"
]

for sql in sql_commands:
    print(f"\nExecuting: {sql}")
    result = subprocess.run(
        cmd + [sql],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✓ Success")
    else:
        print(f"  ✗ Error: {result.stderr}")
        sys.exit(1)

print("\n" + "="*70)
print("DATABASE CLEANED SUCCESSFULLY")
print("\nAll farms, parcels, batches, and farmer data removed.")
print("Admin users preserved.")
print("\nNext: Login to dashboard as admin and create fresh test data")
print("  Dashboard: http://localhost:8080")
print("  Admin: admin@plotra.com / (check .env for password or reset)")
print("="*70)

#!/bin/bash
# Ensures the postgres user password matches the configured value on every startup.
# Runs after PostgreSQL is ready via local socket (no password needed).
psql -U postgres -c "ALTER USER postgres WITH PASSWORD '${POSTGRES_PASSWORD}';" || true

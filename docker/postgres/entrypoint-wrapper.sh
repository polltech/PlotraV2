#!/bin/bash
set -e

# Start postgres using original entrypoint in background
/usr/local/bin/docker-entrypoint.sh postgres "$@" &
PG_PID=$!

# Wait for postgres to accept local connections
until pg_isready -U "${POSTGRES_USER:-postgres}" -q 2>/dev/null; do
    if ! kill -0 $PG_PID 2>/dev/null; then
        echo "[entrypoint-wrapper] Postgres failed to start"
        exit 1
    fi
    sleep 1
done

# Reset password via local socket (peer auth — no password needed)
psql -U "${POSTGRES_USER:-postgres}" \
    -c "ALTER USER ${POSTGRES_USER:-postgres} WITH PASSWORD '${POSTGRES_PASSWORD}';" \
    2>/dev/null && echo "[entrypoint-wrapper] Password synced" || true

# Forward signals and wait
trap "kill -SIGTERM $PG_PID 2>/dev/null" SIGTERM SIGINT
wait $PG_PID

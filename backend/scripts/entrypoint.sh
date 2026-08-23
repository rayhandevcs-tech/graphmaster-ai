#!/usr/bin/env bash
# Container entrypoint: wait for the database, migrate, seed, then serve.
set -euo pipefail

echo "==> Waiting for the database..."
python - <<'PY'
import os, sys, time, urllib.parse as up
import psycopg2

url = up.urlparse(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
for attempt in range(1, 31):
    try:
        psycopg2.connect(
            dbname=url.path.lstrip("/"), user=url.username,
            password=url.password, host=url.hostname, port=url.port or 5432,
        ).close()
        print(f"    database reachable (attempt {attempt})")
        sys.exit(0)
    except psycopg2.OperationalError as exc:
        print(f"    not ready (attempt {attempt}/30): {exc}".strip())
        time.sleep(2)
print("    database did not become reachable in 60s", file=sys.stderr)
sys.exit(1)
PY

echo "==> Applying migrations..."
alembic upgrade head

echo "==> Seeding reference data..."
python -m app.db.seed.cli

echo "==> Starting API..."
exec "$@"

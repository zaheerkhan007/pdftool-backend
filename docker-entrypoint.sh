#!/usr/bin/env bash
# Runs on every container start. Everything here is idempotent, which assumes a
# single backend replica — revisit if this is ever scaled out, since concurrent
# `migrate` runs are not safe.
set -euo pipefail

echo "==> waiting for postgres at ${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}"
python - <<'PY'
import os, socket, sys, time

host = os.environ.get("POSTGRES_HOST", "localhost")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=3):
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"postgres at {host}:{port} did not become reachable in 60s", file=sys.stderr)
sys.exit(1)
PY

echo "==> migrate"
python manage.py migrate --noinput

echo "==> collectstatic"
python manage.py collectstatic --noinput --clear

# Optional: only created when both vars are set, and never overwrites an
# existing user, so rotating the password means doing it in the admin.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
	echo "==> ensuring superuser ${DJANGO_SUPERUSER_USERNAME}"
	python manage.py createsuperuser --noinput 2>/dev/null \
		|| echo "    superuser already exists, leaving it alone"
fi

exec "$@"

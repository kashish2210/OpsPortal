#!/bin/sh
# ---------------------------------------------------------------------------
# Container start-up: wait for the database, migrate, collect static files,
# optionally seed demo data, then hand over to the CMD (gunicorn).
# ---------------------------------------------------------------------------
set -e

echo "==> OpsPortal backend starting"

# -- 1. wait for postgres ---------------------------------------------------
if [ -n "$DATABASE_URL" ]; then
  echo "==> Waiting for the database..."
  attempt=1
  until python - <<'PY'
import os, sys
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.db import connections
from django.db.utils import OperationalError
try:
    connections["default"].cursor()
except OperationalError as exc:
    print(f"    not ready: {exc}", file=sys.stderr)
    sys.exit(1)
PY
  do
    if [ "$attempt" -ge 30 ]; then
      echo "!!! Database did not become available after 30 attempts. Giving up."
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 2
  done
  echo "==> Database is ready."
fi

# -- 2. schema --------------------------------------------------------------
echo "==> Applying migrations"
python manage.py migrate --noinput

# -- 3. static files --------------------------------------------------------
echo "==> Collecting static files"
python manage.py collectstatic --noinput --clear >/dev/null

# -- 4. demo data -----------------------------------------------------------
case "$SEED_DEMO_DATA" in
  [Tt]rue|1|[Yy]es)
    echo "==> Seeding demo data (idempotent)"
    python manage.py seed_demo
    ;;
  *)
    echo "==> Skipping demo data (set SEED_DEMO_DATA=True to enable)"
    ;;
esac

echo "==> Handing over to: $*"
exec "$@"

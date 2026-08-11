#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# OpsPortal launcher for WSL / Linux / macOS / Git Bash.
#
#   ./run.sh            build + start everything (default)
#   ./run.sh logs       tail the logs
#   ./run.sh reseed     wipe and re-seed the demo data
#   ./run.sh help       list every command
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="docker compose"

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker was not found on PATH."
    echo "Install Docker (or Docker Desktop with the WSL 2 backend) and try again."
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but not running. Start it and try again."
    exit 1
  fi
}

banner() {
  cat <<'BANNER'

  OpsPortal - Mini ERP + CRM Operations Portal
  --------------------------------------------
  App .............. http://localhost:8080
  Django auth ...... http://localhost:8080/accounts/login/
  Django admin ..... http://localhost:8080/admin/
  API docs ......... http://localhost:8080/api/docs/

  Logins:  admin / Admin@12345          (Admin)
           sales / Sales@12345          (Sales)
           warehouse / Warehouse@12345  (Warehouse)
           accounts / Accounts@12345    (Accounts)

BANNER
}

case "${1:-up}" in
  help|-h|--help)
    cat <<'USAGE'
Usage: ./run.sh [command]

  up         Build and start the whole stack (default)
  down       Stop the stack, keeping the database
  restart    Restart every service
  logs       Tail the logs
  ps         Show container status
  build      Build the images
  rebuild    Rebuild ignoring the cache
  shell      Shell into the backend container
  dbshell    psql into the database
  migrate    Apply migrations
  seed       Seed demo data
  reseed     Wipe and re-seed demo data
  superuser  Create a Django superuser
  test       Run the backend test suite
  nuke       Stop and DELETE the database volume
USAGE
    ;;
  up)
    require_docker; banner
    echo "Building and starting... (the first run pulls images, give it a few minutes)"
    $COMPOSE up --build
    ;;
  down)      require_docker; $COMPOSE down ;;
  restart)   require_docker; $COMPOSE restart ;;
  logs)      require_docker; $COMPOSE logs -f ;;
  ps)        require_docker; $COMPOSE ps ;;
  build)     require_docker; $COMPOSE build ;;
  rebuild)   require_docker; $COMPOSE build --no-cache ;;
  shell)     require_docker; $COMPOSE exec backend /bin/sh ;;
  dbshell)   require_docker; $COMPOSE exec db psql -U opsportal -d opsportal ;;
  migrate)   require_docker; $COMPOSE exec backend python manage.py migrate ;;
  seed)      require_docker; $COMPOSE exec backend python manage.py seed_demo ;;
  reseed)    require_docker; $COMPOSE exec backend python manage.py seed_demo --reset ;;
  superuser) require_docker; $COMPOSE exec backend python manage.py createsuperuser ;;
  test)      require_docker; $COMPOSE exec backend python manage.py test ;;
  nuke)
    require_docker
    echo "This deletes the database volume and all data in it."
    $COMPOSE down -v
    ;;
  *)
    echo "Unknown command: $1"
    echo "Run './run.sh help' for the list."
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# OpsPortal - common tasks. Run `make help` for the list.
# Works in WSL / Git Bash / macOS / Linux. On plain PowerShell use run.ps1.
# ---------------------------------------------------------------------------

COMPOSE ?= docker compose
PY      ?= python

.DEFAULT_GOAL := help

.PHONY: help up down restart logs ps build rebuild shell dbshell migrate makemigrations seed reseed superuser test check collectstatic clean nuke dev-backend dev-frontend install-backend install-frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# -- Docker -----------------------------------------------------------------
up: ## Build and start the whole stack (http://localhost:8080)
	$(COMPOSE) up --build

down: ## Stop the stack (keeps the database volume)
	$(COMPOSE) down

restart: ## Restart every service
	$(COMPOSE) restart

build: ## Build the images without starting them
	$(COMPOSE) build

rebuild: ## Rebuild from scratch, ignoring the layer cache
	$(COMPOSE) build --no-cache

logs: ## Tail the logs of every service
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

shell: ## Open a shell inside the backend container
	$(COMPOSE) exec backend /bin/sh

dbshell: ## Open psql against the running database
	$(COMPOSE) exec db psql -U opsportal -d opsportal

# -- Django (inside Docker) -------------------------------------------------
migrate: ## Apply migrations in the running backend
	$(COMPOSE) exec backend python manage.py migrate

makemigrations: ## Generate migrations in the running backend
	$(COMPOSE) exec backend python manage.py makemigrations

seed: ## Seed demo data (skips if data already exists)
	$(COMPOSE) exec backend python manage.py seed_demo

reseed: ## Wipe the business data and seed it again
	$(COMPOSE) exec backend python manage.py seed_demo --reset

superuser: ## Create a Django superuser interactively
	$(COMPOSE) exec backend python manage.py createsuperuser

test: ## Run the backend test suite inside Docker
	$(COMPOSE) exec backend python manage.py test

collectstatic: ## Re-collect static files
	$(COMPOSE) exec backend python manage.py collectstatic --noinput

check: ## Django system checks (deployment profile)
	$(COMPOSE) exec backend python manage.py check --deploy

# -- Local development (no Docker) ------------------------------------------
install-backend: ## Create a venv and install the backend requirements
	cd backend && $(PY) -m venv .venv && \
	  .venv/bin/pip install --upgrade pip && \
	  .venv/bin/pip install -r requirements.txt

install-frontend: ## Install the frontend dependencies
	cd frontend && npm install

dev-backend: ## Run the Django dev server on :8000
	cd backend && $(PY) manage.py migrate && $(PY) manage.py runserver 0.0.0.0:8000

dev-frontend: ## Run the Vite dev server on :5173
	cd frontend && npm run dev

# -- Cleanup ----------------------------------------------------------------
clean: ## Remove build artefacts (dist, __pycache__, staticfiles)
	rm -rf frontend/dist backend/staticfiles
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

nuke: ## Stop the stack and DELETE the database volume
	$(COMPOSE) down -v

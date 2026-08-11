# OpsPortal — Mini ERP + CRM Operations Portal

A small ERP/CRM for a wholesale & distribution company: customers (CRM), products
and stock (inventory), and sales challans with real stock-deduction business rules.
Built for the Full Stack Developer case study.

**Django + DRF backend · React (TypeScript) frontend · PostgreSQL · Docker**

```bash
docker compose up --build
```

Then open **<http://localhost:8080>** and sign in as `admin` / `Admin@12345`.

---

## Table of contents

1. [Stack note (deviation from the brief)](#1-stack-note-deviation-from-the-brief)
2. [Quick start](#2-quick-start)
3. [Test logins](#3-test-logins)
4. [What is built](#4-what-is-built)
5. [Architecture](#5-architecture)
6. [Business rules that matter](#6-business-rules-that-matter)
7. [Authentication & the two login surfaces](#7-authentication--the-two-login-surfaces)
8. [Roles & permissions](#8-roles--permissions)
9. [API reference](#9-api-reference)
10. [Local development (WSL + conda/venv)](#10-local-development-wsl--condavenv)
11. [Environment variables](#11-environment-variables)
12. [Server setup & deployment](#12-server-setup--deployment)
13. [Tests](#13-tests)
14. [Project layout](#14-project-layout)
15. [Assumptions](#15-assumptions)
16. [Known limitations & what is not built](#16-known-limitations--what-is-not-built)

---

## 1. Stack note (deviation from the brief)

The case study asks for **Node.js + TypeScript + Express/NestJS** on the backend.
This implementation uses **Django + Django REST Framework** instead, at the
explicit request of the reviewer, together with **Django's built-in auth** for the
server-rendered login pages. Everything else follows the brief: React frontend,
relational database (PostgreSQL), REST APIs with validation, proper status codes,
pagination and search, role-based access, and documented deployment.

The frontend is **React + TypeScript**, so the TypeScript requirement holds there.

---

## 2. Quick start

### With Docker (recommended — one command)

Requirements: Docker Desktop (WSL 2 backend on Windows) or Docker Engine + Compose v2.

```bash
docker compose up --build
```

That single command builds both images, starts PostgreSQL, waits for it to be
healthy, runs migrations, collects static files, seeds demo data, and serves
everything through nginx on one origin.

| URL | What it is |
| --- | --- |
| <http://localhost:8080> | React operations app |
| <http://localhost:8080/accounts/login/> | Django-rendered login (and the rest of the auth pages) |
| <http://localhost:8080/admin/> | Django admin |
| <http://localhost:8080/api/docs/> | Swagger UI |
| <http://localhost:8080/api/redoc/> | ReDoc |
| <http://localhost:8080/api/schema/> | OpenAPI 3 schema (JSON) |
| <http://localhost:8000/api/> | Django directly, for Postman |

Convenience wrappers, if you prefer them to raw `docker compose`:

```bash
./run.sh              # WSL / Linux / macOS / Git Bash
```

```powershell
.\run.ps1
```

```bash
make up
```

Stop with `Ctrl-C`, then:

```bash
docker compose down        # keeps the database
docker compose down -v     # deletes the database volume too
```

### Without Docker

See [Local development](#10-local-development-wsl--condavenv).

---

## 3. Test logins

Created by `manage.py seed_demo`, which the container entrypoint runs
automatically when `SEED_DEMO_DATA=True` (the default).

| Role | Username | Password | Can do |
| --- | --- | --- | --- |
| Admin | `admin` | `Admin@12345` | Everything, including user management |
| Sales | `sales` | `Sales@12345` | Customers + challans (write), products + stock (read) |
| Warehouse | `warehouse` | `Warehouse@12345` | Products + stock (write), customers + challans (read) |
| Accounts | `accounts` | `Accounts@12345` | Read-only across every module |

`admin` is also a Django superuser, so it can reach `/admin/`.

The seed also creates 12 customers, 22 follow-up notes, 20 products across 6
categories (3 of them deliberately low/out of stock), 42 stock movements, and 9
challans — 6 confirmed, 2 draft and 1 cancelled.

---

## 4. What is built

### Authentication and roles ✅
Four roles (Admin, Sales, Warehouse, Accounts). JWT for the API, Django sessions
for the server-rendered pages, and a session→JWT handoff so both work together.
Full Django auth page set: login, signup, logout, password change/set, the
four-step password reset, e-mail management, e-mail confirmation, verification
sent, verification required, account inactive, signup closed.

### Customer CRM ✅
Name, mobile, e-mail, business name, GST number (optional), customer type
(Retail/Wholesale/Distributor), address, status (Lead/Active/Inactive),
follow-up date, notes. Add, edit, search, detail page, and dated follow-up notes
that roll the customer's next-contact date forward.

### Product & inventory ✅
Name, SKU, category, unit price, current stock, minimum stock alert,
location/warehouse (plus unit, HSN and GST rate). Add, edit, and an append-only
stock movement log recording product, quantity changed, IN/OUT, reason, who did
it, when, and the resulting balance.

### Sales challan ✅
Select customer, add multiple products with quantities, automatic challan number,
save as Draft or Confirmed. Confirming reduces stock atomically; stock can never
go negative; insufficient stock returns a proper error; every line stores a
product snapshot rather than just a product ID.

### API ✅
Clean REST endpoints with input validation, correct HTTP status codes, a uniform
error envelope, pagination on every list, and search/filter/ordering throughout.

### Frontend ✅
Clean admin-style React UI, responsive down to mobile, light and dark themes.

### Bonus features ✅
Challan PDF export, product image upload with optional S3 storage, SMTP via
Mailpit, GitHub Actions CI with PR test reporting, a deployment workflow, and
`act` support for local workflow runs.

---

## 5. Architecture

```
                        ┌──────────────────────────────┐
  browser  ──────────►  │  nginx  (frontend container) │  :8080
                        │                              │
                        │  /            → React SPA    │
                        │  /api/        ─┐             │
                        │  /accounts/    │             │
                        │  /admin/       ├─► proxy     │
                        │  /static/      │             │
                        │  /media/      ─┘             │
                        └───────────────┬──────────────┘
                                        │
                        ┌───────────────▼──────────────┐
                        │  gunicorn (backend container)│  :8000
                        │  Django 5.2 + DRF            │
                        │                              │
                        │  accounts │ crm │ inventory  │
                        │           │ sales │ core     │
                        └───────────────┬──────────────┘
                                        │
                        ┌───────────────▼──────────────┐
                        │  PostgreSQL 16 (db container)│  :5432
                        └──────────────────────────────┘
```

**Why one origin.** nginx fronts both the SPA and Django. That means the session
cookie Django sets on its login page is also sent to `/api/auth/session-token/`,
which is what makes the handoff work — and it removes CORS and CSRF friction
entirely. In development the Vite dev server proxies the same paths, so the two
environments behave identically.

**Media uploads.** Product images and avatars are written into a shared Docker
volume. The backend stores them there and nginx serves `/media/` directly when
`DEBUG=False`, so uploads keep working in the production-style compose stack.

**Backend layering.** Views stay thin. The rules that must never break live in
service modules — `inventory/services.py` owns every change to stock, and
`sales/services.py` owns the challan state machine. Both are called from the API,
the seed command and the tests, so there is exactly one implementation of each
rule.

**Django apps**

| App | Responsibility |
| --- | --- |
| `core` | Shared plumbing: pagination, role permissions, error envelope, audit base models, gap-free document numbering, dashboard aggregation, `seed_demo` |
| `accounts` | Custom `User` with a role, JWT endpoints, and the whole server-rendered auth page set |
| `crm` | `Customer`, `FollowUp` |
| `inventory` | `Product`, `StockMovement`, and the stock engine |
| `sales` | `SalesChallan`, `ChallanItem`, and the confirm/cancel state machine |

**Frontend structure**

```
src/
  api/          client (JWT + auto-refresh), typed endpoints, API types
  auth/         AuthContext, route guards, client-side role matrix
  components/   Layout, shared UI kit, toasts, theme toggle
  hooks/        data fetching with cancellation, debounce
  pages/        one folder per module
  styles/       sketch.css — the shared design system
```

---

## 6. Business rules that matter

These are the parts the brief calls out, and where the real work went.

**Stock never goes negative.** Every change to `Product.current_stock` goes
through `inventory/services.py`. It locks the product rows with
`SELECT … FOR UPDATE` *before* reading them, so two sales users confirming
challans at the same instant serialise instead of both passing the check. A short
line raises `InsufficientStockError`; nothing is written.

**All-or-nothing, with every shortage reported.** A challan with three lines where
two are short does not partially ship. The service collects *every* shortage
before raising, so the UI can highlight all the bad lines at once:

```json
{
  "success": false,
  "error": {
    "code": "insufficient_stock",
    "message": "Insufficient stock for: SF-GL-CR (need 10, have 0).",
    "details": {
      "shortages": [
        { "product_id": 17, "sku": "SF-GL-CR", "product_name": "Cut-resistant Gloves (Pair)",
          "requested": 10, "available": 0, "short_by": 10 }
      ]
    }
  }
}
```

**Drafts reserve nothing.** Stock only moves on confirmation. `POST /api/challans/`
with `confirm: true` is all-or-nothing too — a stock failure rolls the challan
back as well, so a 400 never leaves an orphaned draft behind.

**Cancelling is compensating, not destructive.** Cancelling a *confirmed* challan
writes IN movements with reason `CHALLAN_CANCELLED` and returns the stock.
Cancelling a *draft* touches nothing. The ledger stays a faithful record of what
actually happened rather than being edited after the fact.

**Snapshots.** Each challan line copies the product's name, SKU, category, unit,
price and GST rate at save time, and the challan copies the customer's billing
details. Renaming or repricing a product later cannot rewrite an issued document.
There is a test for exactly this.

**Confirmed documents are immutable.** Only drafts can be edited or deleted. A
confirmed challan must be cancelled and re-raised — enforced in the API, the
service layer *and* Django admin.

**Document numbers don't collide.** `MAX(id) + 1` breaks under concurrency, so
numbering uses a locked counter table (`core/sequences.py`). Challan numbers are
`CH-YYYYMM-00001` and restart each month; customers get `CUST-00001`.

**Stock is a ledger, not a field.** `Product.current_stock` is a running balance;
`StockMovement` explains every change to it and stores the balance after each
one. `recalculate_stock()` can rebuild the balance from the ledger to reconcile
the two. Movement rows cannot be edited or deleted, including in admin.

---

## 7. Authentication & the two login surfaces

There are two ways in, and they share one user table and one session.

**1. The React login** (`/login`) posts to `POST /api/auth/login/` and stores a
JWT pair. Access tokens last 60 minutes; the client refreshes them transparently
on a 401 and replays the request. Refresh tokens rotate and the old one is
blacklisted.

**2. The Django-rendered pages** (`/accounts/…`) use `django.contrib.auth` with
sessions. After signing in, the profile page has an **Open OpsPortal →** button
that lands on `/auth/handoff`, which calls `POST /api/auth/session-token/`. That
endpoint authenticates via the session cookie and returns a JWT pair, so the SPA
picks up the session without a second login.

Both accept **username or e-mail** (`accounts/backends.py`).

### Every Django auth page

All of them are styled with the shared hand-drawn design system and are reachable:

| URL | Page |
| --- | --- |
| `/accounts/login/` | Login |
| `/accounts/signup/` | Sign up (with avatar cropper) |
| `/accounts/signup/closed/` | Sign-up closed (when `SIGNUP_OPEN=False`) |
| `/accounts/logout/` | Sign-out confirmation → signed-out page |
| `/accounts/profile/` | Profile, edit details, and the SPA handoff |
| `/accounts/password/change/` | Change password → done |
| `/accounts/password/set/` | Set a password (accounts without one) |
| `/accounts/password/reset/` | Request a reset |
| `/accounts/password/reset/sent/` | Reset link sent |
| `/accounts/password/reset/key/<uid>/<token>/` | Choose a new password |
| `/accounts/password/reset/complete/` | Password updated |
| `/accounts/email/` | Manage e-mail address, re-send verification |
| `/accounts/email/confirm/<uid>/<token>/` | Confirm e-mail address |
| `/accounts/email/sent/` | Verification sent |
| `/accounts/email/required/` | Verified e-mail required |
| `/accounts/inactive/` | Account deactivated |

With the console e-mail backend (the default), password-reset and verification
e-mails are printed to the backend logs:

```bash
docker compose logs -f backend
```

Copy the link from there to walk through the reset flow.

---

## 8. Roles & permissions

Declared once per viewset via `core/permissions.RolePermission`, and mirrored in
the frontend (`src/auth/permissions.ts`) purely to decide what to *offer* — the
server is always the enforcer.

| Module | Admin | Sales | Warehouse | Accounts |
| --- | --- | --- | --- | --- |
| Customers / follow-ups | read + write | read + write | read | read |
| Products | read + write | read | read + write | read |
| Stock movements | read + write | read | read + write | read |
| Sales challans | read + write | read + write | read | read |
| Users & roles | full | – | – | – |

A denied write returns `403` with
`{"error": {"code": "permission_denied", …}}`.

---

## 9. API reference

Interactive docs: **<http://localhost:8080/api/docs/>** (Swagger UI, generated
from the code by drf-spectacular). A Postman collection is at
[`docs/OpsPortal.postman_collection.json`](docs/OpsPortal.postman_collection.json) —
import it, run **Auth → Login**, and its test script stores the token for every
other request automatically.

### Conventions

Every list endpoint is paginated:

```json
{ "count": 137, "page": 2, "page_size": 20, "total_pages": 7,
  "next": "...", "previous": "...", "results": [] }
```

Common query parameters: `?q=` (free text), `?page=`, `?page_size=` (max 200),
`?ordering=` (prefix `-` to reverse), plus per-resource filters.

Every error uses one envelope:

```json
{ "success": false,
  "error": { "code": "validation_error", "message": "...", "details": { "field": ["..."] } } }
```

Status codes: `200` ok · `201` created · `204` deleted · `205` logged out ·
`400` validation or business-rule failure · `401` missing/expired token ·
`403` role not allowed · `404` not found · `429` throttled.

### Endpoints

**Auth**

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/auth/login/` | `{username, password}` — username *or* e-mail → `{access, refresh, user}` |
| POST | `/api/auth/refresh/` | `{refresh}` → `{access, refresh}` |
| POST | `/api/auth/logout/` | `{refresh}` — blacklists it |
| GET/PATCH | `/api/auth/me/` | Current user; PATCH edits own details (not the role) |
| POST | `/api/auth/change-password/` | `{old_password, new_password}` |
| POST | `/api/auth/session-token/` | Django session → JWT pair |

**Customers** — `?q= &status= &customer_type= &city= &has_gst= &follow_up=due|upcoming|none`

| Method | Path |
| --- | --- |
| GET / POST | `/api/customers/` |
| GET / PATCH / DELETE | `/api/customers/{id}/` (DELETE marks inactive) |
| GET / POST | `/api/customers/{id}/follow-ups/` |
| GET | `/api/customers/options/`, `/stats/`, `/choices/` |
| GET / POST | `/api/follow-ups/` |

**Products & stock** — `?q= &category= &location= &stock=low|out|in &is_active=`

| Method | Path |
| --- | --- |
| GET / POST | `/api/products/` (`opening_stock` on create logs an OPENING movement) |
| GET / PATCH / DELETE | `/api/products/{id}/` (DELETE archives) |
| GET | `/api/products/{id}/movements/` |
| POST | `/api/products/{id}/adjust-stock/` — `{new_quantity, notes}` stock-take |
| GET | `/api/products/low-stock/`, `/categories/`, `/locations/`, `/stats/`, `/choices/`, `/options/` |
| GET / POST | `/api/stock-movements/` — `?product= &sku= &movement_type= &reason= &reference= &created_after= &created_before=` |

**Challans** — `?q= &status= &customer= &date_from= &date_to= &product=`

| Method | Path |
| --- | --- |
| GET / POST | `/api/challans/` (`confirm: true` saves *and* confirms) |
| GET / PATCH / DELETE | `/api/challans/{id}/` (drafts only) |
| POST | `/api/challans/{id}/confirm/` — deducts stock |
| POST | `/api/challans/{id}/cancel/` — `{reason}`; restores stock if confirmed |
| GET | `/api/challans/{id}/stock-movements/`, `/api/challans/stats/` |

**Users (admin)** — `/api/users/`, `/api/users/{id}/`, `/activate/`,
`/deactivate/`, `/api/users/roles/`

**Other** — `GET /api/dashboard/`, `GET /api/health/` (public)

### Worked example

```bash
# 1. log in
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"sales","password":"Sales@12345"}' | jq -r .access)

# 2. raise and confirm a challan in one request
curl -s -X POST http://localhost:8000/api/challans/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"customer": 1, "confirm": true,
       "items": [{"product": 1, "quantity": 5}]}' | jq

# 3. ask for more than exists -> 400 insufficient_stock, nothing written
curl -s -X POST http://localhost:8000/api/challans/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"customer": 1, "confirm": true,
       "items": [{"product": 1, "quantity": 999999}]}' | jq
```

---

## 10. Local development (WSL + conda/venv)

Docker is the shortest path, but the project runs natively too. The backend falls
back to **SQLite** when `DATABASE_URL` is empty, so no database setup is needed.

### Backend — conda (matches the Docker image's Python 3.12)

```bash
conda create -n opsportal python=3.12 -y
conda activate opsportal

cd backend
pip install -r requirements.txt
cp .env.example .env          # optional; defaults work

python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

### Backend — plain venv

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Vite proxies `/api`, `/accounts`, `/admin`, `/static` and `/media` to
`http://127.0.0.1:8000`, so the SPA and the Django pages share an origin exactly
as they do behind nginx. Point it elsewhere with `VITE_PROXY_TARGET`.

### WSL notes

Docker Desktop must have **WSL 2 integration** enabled for your distro
(*Settings → Resources → WSL Integration*). Then, inside WSL:

```bash
cd /mnt/k/'Fundsroom Infotech Process'
./run.sh
```

For native (non-Docker) work, **clone into the Linux filesystem**
(`~/projects/…`) rather than working under `/mnt/k`. Cross-filesystem I/O makes
`npm install` and Django's autoreloader dramatically slower, and file-watching is
unreliable across the boundary.

Ports published by Compose are reachable from Windows at `localhost` — no extra
port forwarding.

---

## 11. Environment variables

Nothing secret is hard-coded. The backend reads everything through
`django-environ`, loading `backend/.env` or the repository-root `.env` when
present, and falling back to safe defaults.

- **Docker**: `docker-compose.yml` supplies each value with a default; override
  by copying [`.env.example`](.env.example) to `.env`.
- **Local**: copy [`backend/.env.example`](backend/.env.example) to `backend/.env`.
- **Frontend**: build-time `VITE_*` variables, see
  [`frontend/.env.example`](frontend/.env.example). Leave the base URLs empty for
  same-origin requests (correct for both Docker and the dev proxy).

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEBUG` | `False` | Never enable in production |
| `SECRET_KEY` | dev placeholder | **Must** be replaced when deploying |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend,frontend` | Comma-separated |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8080` | Needed for the Django forms |
| `DATABASE_URL` | *(empty → SQLite)* | `postgres://user:pass@host:5432/db` |
| `FRONTEND_URL` | `http://localhost:8080` | Where the handoff button points |
| `CORS_ALLOWED_ORIGINS` | localhost:8080, :5173 | Only needed for split origins |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | `60` | |
| `REFRESH_TOKEN_LIFETIME_DAYS` | `7` | Rotated + blacklisted on use |
| `SIGNUP_OPEN` | `True` | `False` shows the "sign-up closed" page |
| `REQUIRE_EMAIL_VERIFICATION` | `False` | `True` gates login behind confirmation |
| `EMAIL_BACKEND` | console | Switch to SMTP for real delivery |
| `SEED_DEMO_DATA` | `True` | Entrypoint runs `seed_demo` |
| `SECURE_SSL_REDIRECT` | `False` | Turn on behind HTTPS |

Generate a production key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## 12. Server setup & deployment

### How the server is set up

The backend image is `python:3.12-slim`. It installs the pinned requirements,
copies the project, creates a non-root `appuser`, and exposes `:8000`. The
entrypoint (`backend/entrypoint.sh`) runs on every start and:

1. waits for PostgreSQL (30 attempts, 2 s apart) — so `docker compose up` works
   from cold with no ordering races;
2. applies migrations;
3. runs `collectstatic` into a named volume;
4. seeds demo data when `SEED_DEMO_DATA=True` (idempotent — safe to re-run);
5. execs gunicorn (3 workers × 2 threads, 60 s timeout).

Static files are served by WhiteNoise with hashed, compressed filenames.
`/api/health/` backs the container healthcheck, and `frontend` waits on
`service_healthy` so nginx never starts in front of a dead backend.

The frontend image is a two-stage build: `node:22-alpine` runs `npm ci && npm run
build`, then the static `dist/` is copied into `nginx:1.27-alpine`. The runtime
image contains no Node and no source.

### Deploying to a free host (Render / Railway / Fly.io + Neon / Supabase)

**Database** — create a managed PostgreSQL instance and copy its connection URL.

**Backend** — deploy `backend/` as a Docker service and set:

```
DEBUG=False
SECRET_KEY=<generated>
DATABASE_URL=<managed postgres url>
ALLOWED_HOSTS=your-api.onrender.com
CSRF_TRUSTED_ORIGINS=https://your-app.vercel.app,https://your-api.onrender.com
FRONTEND_URL=https://your-app.vercel.app
CORS_ALLOWED_ORIGINS=https://your-app.vercel.app
SECURE_SSL_REDIRECT=True
SEED_DEMO_DATA=True
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=... EMAIL_HOST_USER=... EMAIL_HOST_PASSWORD=...
```

Migrations and seeding run themselves through the entrypoint.

**Frontend** — deploy `frontend/` to Vercel/Netlify with build `npm run build`
and output `dist`. Set `VITE_API_BASE_URL` and `VITE_DJANGO_BASE_URL` to the
backend's URL.

> **Split-origin caveat.** On separate domains the JWT login works fine, but the
> session→JWT handoff needs a cookie that survives cross-site, which means
> `SESSION_COOKIE_SAMESITE="None"` and `SESSION_COOKIE_SECURE=True` over HTTPS.
> The simpler and recommended option is to deploy the Compose stack as one unit
> (Render/Railway/Fly all support it) and keep the single origin — everything
> then works exactly as it does locally.

**AWS (bonus, optional).** The same images run on ECS Fargate behind an ALB with
RDS PostgreSQL, or on a single EC2 box with `docker compose up -d` and Caddy or
nginx terminating TLS.

---

## 13. Tests

Backend tests covering the stock engine, the challan state machine, snapshot
integrity, CRM validation, role permissions, JWT auth and every rendered auth
page.

```bash
docker compose exec backend python manage.py test          # in Docker
cd backend && python manage.py test                        # locally
```

```
Ran 123 tests in 54.8s
OK
```

Frontend type safety:

```bash
cd frontend && npm run typecheck
```

### Running GitHub Actions locally

This repo is wired for [nektos/act](https://github.com/nektos/act), not the
older Snap package also named `act`. If `act` segfaults immediately in WSL,
check `which act` and make sure it points to the nektos binary rather than
`/snap/bin/act`.

If `act` then stops while cloning GitHub Actions, make sure `.secrets` does not
contain a placeholder token. For a normal local dry-run, `GITHUB_TOKEN` can be
left blank. Only set a real token if you want the PR comment steps to talk to
GitHub on a real pull request.

Recommended install on Linux / WSL:

```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

Then run the binary that was installed into the repo, or add `bin/` to PATH:

```bash
./bin/act pull_request
# or: export PATH="$PWD/bin:$PATH" && act pull_request
```

---

## 14. Project layout

```
.
├── docker-compose.yml          one command to run everything
├── .env.example                compose environment
├── Makefile / run.sh / run.ps1 task wrappers
├── backend/
│   ├── config/                 settings (env-driven), urls, wsgi/asgi
│   ├── core/                   pagination, permissions, errors, sequences,
│   │                           dashboard, seed_demo
│   ├── accounts/               User + roles, JWT API, Django auth views
│   ├── crm/                    Customer, FollowUp
│   ├── inventory/              Product, StockMovement, stock engine
│   ├── sales/                  SalesChallan, ChallanItem, state machine
│   ├── templates/registration/ every auth page
│   ├── static/css/sketch.css   the design system
│   ├── Dockerfile, entrypoint.sh, requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/{api,auth,components,hooks,pages,styles}
│   ├── Dockerfile, nginx.conf, nginx-proxy.inc
│   └── package.json, vite.config.ts, .env.example
└── docs/
    ├── OpsPortal.postman_collection.json
    └── Full Stack Developer Case Study (1).pdf
```

---

## 15. Assumptions

1. **Django instead of Node.** Requested explicitly by the reviewer; see §1.
2. **One role per user.** A small distribution company's staff sit in one team.
   Multiple roles would need a many-to-many and a permission union.
3. **Mobile number is unique per customer.** It is the field staff actually search
   by, and duplicate CRM records for one number are the classic data-quality
   problem. Relax `unique=True` on `crm.Customer.mobile` if a shared office line
   must be allowed.
4. **GST is mandatory for wholesale and distributor customers**, optional for
   retail — those two invoice against a GSTIN.
5. **New leads need a follow-up date.** A lead with no next action gets forgotten.
6. **Self-service signup creates an active Sales user**, and an admin changes the
   role afterwards. Set `SIGNUP_OPEN=False` for an invite-only deployment.
7. **Nothing is hard-deleted.** Customers go Inactive, products Archived, users
   Deactivated — challans and the stock ledger reference them for audit. Only
   draft challans can truly be deleted.
8. **Cancelling a confirmed challan returns the stock in full.** Partial returns
   would need a separate sales-return document.
9. **Prices are exclusive of GST**, and tax is computed per line from the
   product's rate. No CGST/SGST/IGST split — that needs place-of-supply logic.
10. **Line prices may be overridden** on a challan (negotiated rates); the
    snapshot then keeps the agreed price, not the catalogue one.
11. **Currency is INR** and the timezone `Asia/Kolkata` (both configurable).
12. **E-mail verification is off by default** so the demo has no friction. Turn on
    `REQUIRE_EMAIL_VERIFICATION` and point `EMAIL_BACKEND` at SMTP for production.

---

## 16. Known limitations & what is not built

**Deliberately out of scope.** The brief lists four core modules; purchase orders
and invoices appear only in the scene-setting paragraph, so they are not built.
The bonus items requested for this repo are built in: PDF export, product image
uploads, SMTP delivery, and GitHub Actions CI/CD. Docker is included because it
was explicitly requested.

**Known limitations**

- **No live deployment URL.** The submission is the Docker stack plus this README;
  §12 documents exactly how to deploy it.
- **No frontend unit tests.** TypeScript in strict mode plus the backend test
  suite carry the correctness load; component tests would be the next addition.
- **Dashboard aggregates are computed per request.** Fine at this data volume;
  a large dataset would want caching or materialised counters.
- **Search is `ILIKE`-based.** Good to a few hundred thousand rows; beyond that
  use PostgreSQL full-text search or a trigram index.
- **No CSV import/export.** Would be a natural next step for both customers and
  products.
- **No audit trail of field-level edits.** Rows carry `created_by`/`updated_by`
  and timestamps, but not a full change history.
- **Single-warehouse semantics.** `location` is a label on the product, not a
  separate stock balance per warehouse; real multi-warehouse stock needs a
  per-location quantity table.
- **The session→JWT handoff assumes a single origin** (see §12).
- **No rate limiting beyond login and password reset**, which are throttled at
  20/min and 10/hour.

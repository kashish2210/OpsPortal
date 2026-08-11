# OpsPortal — Architecture

All diagrams are Mermaid, which GitHub renders natively in Markdown.

---

## 1. System overview

Everything is served through nginx on a single origin, so the session cookie
Django sets on its login page is also sent to `/api/auth/session-token/`. That is
what makes the SPA handoff work — and it removes CORS and CSRF friction entirely.

```mermaid
flowchart TB
    browser["Browser"]

    subgraph frontend_c["frontend container - nginx :80"]
        spa["React SPA<br/>(static build)"]
        proxy["reverse proxy"]
    end

    subgraph backend_c["backend container - gunicorn :8000"]
        django["Django 5.2 + DRF"]
        accounts["accounts<br/>users, roles, JWT, auth pages"]
        crm["crm<br/>customers, follow-ups"]
        inventory["inventory<br/>products, stock ledger"]
        sales["sales<br/>challans, PDF"]
        core["core<br/>permissions, pagination,<br/>errors, sequences"]
    end

    db[("PostgreSQL 16")]
    mail["Mailpit<br/>SMTP :1025 / inbox :8025"]
    s3[("Amazon S3<br/>optional, USE_S3=True")]

    browser -->|"/ static assets"| spa
    browser -->|"/api /accounts /admin /static /media"| proxy
    proxy --> django

    django --> accounts
    django --> crm
    django --> inventory
    django --> sales
    accounts -.-> core
    crm -.-> core
    inventory -.-> core
    sales -.-> core

    django --> db
    django -->|"password reset,<br/>verification"| mail
    django -.->|"product images"| s3
```

---

## 2. Request paths through nginx

```mermaid
flowchart LR
    req["Incoming request"] --> router{"path"}
    router -->|"/api/**"| api["Django REST API<br/>JWT bearer"]
    router -->|"/accounts/**"| auth["Django auth pages<br/>session cookie"]
    router -->|"/admin/**"| admin["Django admin"]
    router -->|"/static/** /media/**"| files["WhiteNoise / media volume"]
    router -->|"everything else"| spa["index.html<br/>(SPA history fallback)"]
```

---

## 3. Authentication — two surfaces, one session

```mermaid
sequenceDiagram
    actor U as User
    participant SPA as React SPA
    participant DJ as Django auth pages
    participant API as REST API
    participant DB as PostgreSQL

    rect rgb(240, 246, 252)
    note over U,API: Route A - sign in inside the app
    U->>SPA: /login form
    SPA->>API: POST /api/auth/login/
    API->>DB: verify credentials
    API-->>SPA: access + refresh JWT + user
    SPA->>SPA: store tokens, render dashboard
    end

    rect rgb(245, 240, 252)
    note over U,API: Route B - sign in on the Django page
    U->>DJ: POST /accounts/login/
    DJ->>DB: verify credentials
    DJ-->>U: session cookie, redirect to profile
    U->>SPA: click "Open OpsPortal" -> /auth/handoff
    SPA->>API: POST /api/auth/session-token/ (cookie)
    API-->>SPA: access + refresh JWT + user
    SPA->>SPA: store tokens, render dashboard
    end

    rect rgb(252, 246, 240)
    note over SPA,API: Silent refresh
    SPA->>API: GET /api/customers/ (expired access)
    API-->>SPA: 401
    SPA->>API: POST /api/auth/refresh/
    API-->>SPA: new access (refresh rotated, old blacklisted)
    SPA->>API: retry the original request
    API-->>SPA: 200
    end
```

---

## 4. Challan state machine

Stock only moves on the transitions marked in bold. A draft reserves nothing.

```mermaid
stateDiagram-v2
    [*] --> DRAFT: create challan

    DRAFT --> CONFIRMED: confirm<br/><b>stock OUT, reason=SALE</b>
    DRAFT --> CANCELLED: cancel<br/>(no stock effect)
    DRAFT --> [*]: delete (drafts only)

    CONFIRMED --> CANCELLED: cancel<br/><b>stock IN, reason=CHALLAN_CANCELLED</b>

    CANCELLED --> [*]

    note right of DRAFT
        Editable. Lines can be
        replaced wholesale.
    end note

    note right of CONFIRMED
        Immutable. PATCH and
        DELETE both return 400.
    end note
```

---

## 5. Confirming a challan — the concurrency-safe path

Two sales users clicking *Confirm* at the same instant serialise on the product
row locks instead of both passing the stock check.

```mermaid
sequenceDiagram
    participant C as Client
    participant V as SalesChallanViewSet
    participant S as sales.services
    participant I as inventory.services
    participant DB as PostgreSQL

    C->>V: POST /api/challans/{id}/confirm/
    V->>S: confirm_challan(challan, user)

    S->>DB: BEGIN
    S->>DB: SELECT ... FOR UPDATE (challan row)
    S->>S: reject if already CONFIRMED / CANCELLED / empty

    S->>I: apply_movements(lines, OUT, reason=SALE)
    I->>DB: SELECT ... FOR UPDATE (products, ordered by pk)
    I->>I: merge duplicate lines, check every quantity

    alt any line is short
        I-->>S: raise InsufficientStockError(shortages=[...])
        S->>DB: ROLLBACK
        V-->>C: 400 insufficient_stock + per-line breakdown
    else all lines fulfillable
        I->>DB: UPDATE products SET current_stock -= qty
        I->>DB: INSERT stock movements (balance_after)
        S->>DB: UPDATE challan SET status=CONFIRMED, confirmed_by, confirmed_at
        S->>DB: COMMIT
        V-->>C: 200 + the confirmed challan
    end
```

---

## 6. Data model

```mermaid
erDiagram
    USER ||--o{ CUSTOMER : "created_by"
    USER ||--o{ FOLLOWUP : "recorded_by"
    USER ||--o{ PRODUCT : "created_by"
    USER ||--o{ STOCKMOVEMENT : "created_by"
    USER ||--o{ SALESCHALLAN : "created_by"

    CUSTOMER ||--o{ FOLLOWUP : has
    CUSTOMER ||--o{ SALESCHALLAN : "billed to"

    PRODUCT ||--o{ STOCKMOVEMENT : "ledger of"
    PRODUCT ||--o{ CHALLANITEM : "referenced by"

    SALESCHALLAN ||--|{ CHALLANITEM : contains

    USER {
        string username UK
        string email UK
        string role "ADMIN|SALES|WAREHOUSE|ACCOUNTS"
        bool is_active
        bool is_email_verified
    }

    CUSTOMER {
        string code UK "CUST-00001"
        string name
        string mobile UK
        string business_name
        string gst_number "required for wholesale"
        string customer_type "RETAIL|WHOLESALE|DISTRIBUTOR"
        string status "LEAD|ACTIVE|INACTIVE"
        date follow_up_date
    }

    FOLLOWUP {
        text note
        string channel
        date next_follow_up_date
    }

    PRODUCT {
        string sku UK
        string name
        string category
        decimal unit_price
        int current_stock "maintained by the ledger"
        int min_stock_alert
        string location
        image image "local or S3"
    }

    STOCKMOVEMENT {
        string movement_type "IN|OUT"
        int quantity
        string reason
        string reference "challan no."
        int balance_after
        datetime created_at
    }

    SALESCHALLAN {
        string challan_number UK "CH-YYYYMM-00001"
        date challan_date
        string status "DRAFT|CONFIRMED|CANCELLED"
        string customer_name "snapshot"
        string customer_gst_number "snapshot"
        int total_quantity
        decimal grand_total
    }

    CHALLANITEM {
        string product_sku "snapshot"
        string product_name "snapshot"
        decimal unit_price "snapshot"
        int quantity
        decimal line_total
    }
```

**Why the snapshot columns.** `CHALLANITEM` copies the product's name, SKU,
category, unit and price at save time, and `SALESCHALLAN` copies the customer's
billing details. Renaming or repricing a product later must never rewrite an
already-issued document — there is a test for exactly this.

---

## 7. Role permission matrix

```mermaid
flowchart LR
    admin(["Admin"])
    sales(["Sales"])
    warehouse(["Warehouse"])
    accounts(["Accounts"])

    customers["Customers<br/>& follow-ups"]
    products["Products"]
    stock["Stock movements"]
    challans["Sales challans"]
    users["Users & roles"]

    admin -->|"read + write"| customers
    admin -->|"read + write"| products
    admin -->|"read + write"| stock
    admin -->|"read + write"| challans
    admin -->|"full"| users

    sales -->|"read + write"| customers
    sales -->|"read + write"| challans
    sales -.->|"read only"| products
    sales -.->|"read only"| stock

    warehouse -->|"read + write"| products
    warehouse -->|"read + write"| stock
    warehouse -.->|"read only"| customers
    warehouse -.->|"read only"| challans

    accounts -.->|"read only"| customers
    accounts -.->|"read only"| products
    accounts -.->|"read only"| stock
    accounts -.->|"read only"| challans
```

Declared once per viewset via `core.permissions.RolePermission` and mirrored in
`frontend/src/auth/permissions.ts` — the frontend copy only decides what to
*offer*; the server is always the enforcer.

---

## 8. CI/CD pipeline

```mermaid
flowchart TB
    push["push / pull request"] --> ci{"CI workflow"}

    ci --> lint["lint<br/>ruff check + format"]
    ci --> be["backend-tests<br/>155 tests vs PostgreSQL 16<br/>coverage + JUnit XML"]
    ci --> fe["frontend-build<br/>tsc typecheck + vite build"]
    ci --> dk["docker-build<br/>docker compose build"]

    be --> report["report job"]
    report --> c1["Backend test results check<br/>(pass/fail counts,<br/>failures annotated on the diff)"]
    report --> c2["Sticky PR comment<br/>(status + coverage %)"]

    lint --> gate{"all green?"}
    be --> gate
    fe --> gate
    dk --> gate

    gate -->|no| block["PR blocked"]
    gate -->|yes| merge["merge to main"]

    merge --> cd{"CD workflow"}
    cd --> imgs["build + push images to GHCR<br/>backend & frontend"]
    imgs --> hook["deploy hook"]
    hook --> smoke["smoke-test /api/health/"]
```

---

## 9. Local development topology

```mermaid
flowchart LR
    subgraph docker["Docker (one command)"]
        n["nginx :8080"] --> g["gunicorn :8000"]
        g --> p[("postgres :5432")]
        g --> m["mailpit :1025<br/>inbox :8025"]
    end

    subgraph native["Native (WSL + conda/venv)"]
        v["vite dev :5173"] -->|"proxy /api /accounts<br/>/admin /static /media"| d["runserver :8000"]
        d --> s[("sqlite db.sqlite3")]
        d --> con["console e-mail backend"]
    end
```

The Vite dev proxy forwards the same paths nginx does, so the two environments
behave identically — including the session→JWT handoff.

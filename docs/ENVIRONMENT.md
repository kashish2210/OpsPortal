# Environment variables — audit & where to get the values

Status of every variable, and exactly where to obtain the ones that are blank.

**Nothing below is required to run the project.** `docker compose up --build`
works with the values already committed — every blank is either an opt-in
feature that is switched off, or something Docker supplies itself. This document
exists so you know what to fill in *when* you want a given feature.

Legend: ✅ set · ⚪ deliberately blank (feature off) · ⚙️ omitted, safe default in code · 🔴 needs action

---

## 1. Quick verdict

| # | Item | State | Action |
| --- | --- | --- | --- |
| 1 | `EMAIL_HOST_USER/PASSWORD` | ✅ | Gmail app password configured and verified with a live send (§3) |
| 2 | `.secrets` (for `act`) | 🔴 | `cp .github/act.secrets.example .secrets` — `.actrc` points at it, so `act` errors without it |
| 3 | `COMPANY_*` | 🔴 | Placeholder company on the challan PDF. Replace with the real details before submitting |
| 4 | `SECRET_KEY` in `.env.example` | 🔴 for prod | Placeholder. Your local `.env` already has a generated one; generate a fresh one per deployment |
| 5 | `POSTGRES_PASSWORD=opsportal` | 🔴 for prod | Fine locally, must change in production |
| 6 | `AWS_*` (Cloudflare R2) | ⚪ | Blank — `USE_S3=False`. Three values to fill in, block pre-staged in `.env` (§4) |
| 7 | `backend/.env`, `frontend/.env` | ⚪ | Only needed for non-Docker dev (§6) |
| 8 | `RENDER_DEPLOY_HOOK_URL`, `HEALTHCHECK_URL` | ⚪ | Only needed to make the CD workflow actually deploy (§5) |
| 9 | `DATABASE_URL` and 6 others | ⚙️ | Absent from `.env` by design; see §7 |

---

## 2. The one thing that is actually broken

`.actrc` contains `--secret-file .secrets`, and `act` fails if that file does not
exist. It is gitignored, so it never arrives with a clone:

```bash
cp .github/act.secrets.example .secrets
```

Leave both values blank for a normal local run — the workflows skip every step
that needs the GitHub API when `ACT` is set.

---

## 3. SMTP — `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`

**This machine is configured for real Gmail delivery.** The local `.env` sends
through `smtp.gmail.com:587` with an app password, verified end to end with a
live password-reset e-mail.

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<16-char app password, spaces removed>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=OpsPortal <you@gmail.com>
```

Gmail notes:

- The password is a **16-character app password** from
  [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
  which requires 2-Step Verification to be on. Your normal account password will
  not authenticate. Google displays it in four groups for readability — **remove
  the spaces**.
- `DEFAULT_FROM_EMAIL` must be the authenticated account (or a verified alias).
  A made-up domain like `no-reply@opsportal.local` gets rewritten or rejected.
- Rough limit: ~500 recipients/day. Plenty for a demo, not for production.
- Treat the app password as a live secret: it lives only in the gitignored
  `.env`, and it can be revoked from the same page that issued it.

**To switch back to Mailpit** (no real mail, visible inbox at
<http://localhost:8025>) set `EMAIL_HOST=mailpit`, `EMAIL_PORT=1025`,
`EMAIL_USE_TLS=False` and clear the user/password. The Mailpit container is
still in `docker-compose.yml`, so a fresh clone works with no credentials at
all — `.env.example` ships pointing at it.

### Alternatives with a free tier

Better than Gmail for anything beyond a demo, since they give you a real sending
domain, bounce handling and deliverability reporting:

| Provider | Free tier | Where to get the credentials |
| --- | --- | --- |
| **Brevo** (ex-Sendinblue) | 300 e-mails/day, no card | [brevo.com](https://www.brevo.com) → sign up → **SMTP & API** → **SMTP** tab. `EMAIL_HOST_USER` is the login shown there (`…@smtp-brevo.com`), `EMAIL_HOST_PASSWORD` is the **SMTP key** — not your account password |
| **Resend** | 3,000/month, 100/day | [resend.com](https://resend.com) → **API Keys** → create. Host `smtp.resend.com`, user is literally `resend`, password is the API key |
| **SendGrid** | 100/day | [sendgrid.com](https://sendgrid.com) → **Settings → API Keys** → Create (Full Access). `EMAIL_HOST_USER` is the literal string `apikey`; password is the key (`SG.…`) |
| **Mailtrap** | dev inbox, not real delivery | [mailtrap.io](https://mailtrap.io) → **Inboxes → SMTP Settings** → copy user/pass. A hosted Mailpit, essentially |
| **Gmail** | ~500/day | Needs 2-Step Verification on, then [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Use the 16-character app password — your normal password will not work |
| **Amazon SES** | 3,000 msg/month (12 mo) | AWS Console → **SES → SMTP settings → Create SMTP credentials** (this makes a dedicated IAM user). Note: new accounts are sandboxed and can only send to verified addresses until you request production access |

Ready-made blocks for each are commented out in [`.env.example`](../.env.example).
For example, Brevo:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-login@smtp-brevo.com
EMAIL_HOST_PASSWORD=your-smtp-key
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=OpsPortal <no-reply@yourdomain.com>
```

Two gotchas:

- **Port 587 → `EMAIL_USE_TLS=True`. Port 465 → `EMAIL_USE_SSL=True`.** Never
  both; `settings.py` force-disables SSL if you set both, but get it right.
- Most providers reject a `DEFAULT_FROM_EMAIL` on a domain you have not
  verified. Verify the sender domain, or use the address they issue you.

Test it without touching the UI:

```bash
docker compose exec backend python manage.py sendtestemail you@example.com
```

---

## 4. Object storage for media — `AWS_*` (Cloudflare R2)

**Currently blank, and that is correct.** `USE_S3=False`, so product images and
avatars go to the local `media_files` Docker volume. The variables keep their
`AWS_` names because that is what `django-storages` reads — the backend works
with any S3-compatible provider, not just Amazon.

### Why R2 rather than S3

| | Cloudflare R2 | Amazon S3 |
| --- | --- | --- |
| Free storage | **10 GB, permanently** | 5 GB, first 12 months only |
| Egress (bandwidth) | **$0, always** | ~$0.09/GB after 100 GB/month |
| Card required to start | No | Yes |
| After the free tier | $0.015/GB-month | $0.023/GB-month |

Product images get read far more than written, so "no egress fees" is the line
that matters. A commented-out R2 block is already staged in your `.env` — three
values to fill in.

### Getting the three values

1. **Create the bucket.** [dash.cloudflare.com](https://dash.cloudflare.com) →
   **R2 Object Storage** in the sidebar → *Create bucket*. Name it
   `opsportal-media`. Location: *Automatic* is fine.
   → this name is `AWS_STORAGE_BUCKET_NAME`.

2. **Account ID → the endpoint.** On the R2 overview page, copy the **Account
   ID** from the right-hand panel. Your endpoint is:

   ```
   https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

   → `AWS_S3_ENDPOINT_URL`.

3. **API token → the key pair.** R2 → **Manage API Tokens** → *Create API
   token*:
   - Permission: **Object Read & Write**
   - Scope it to the single `opsportal-media` bucket, not "all buckets" — if the
     key leaks, the damage is limited to that one bucket
   - TTL: whatever suits you

   Cloudflare then shows an **Access Key ID** and a **Secret Access Key**. The
   secret is displayed **once** — copy it now.
   → `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

### The resulting config

```env
USE_S3=True
AWS_ACCESS_KEY_ID=<Access Key ID>
AWS_SECRET_ACCESS_KEY=<Secret Access Key>
AWS_STORAGE_BUCKET_NAME=opsportal-media
AWS_S3_REGION_NAME=auto
AWS_S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

Then `docker compose up -d backend` and upload an image on any product page.

### Three R2 gotchas, all already handled in `settings.py`

1. **Region must be the literal string `auto`.** R2 has no regions; boto3 still
   demands the field. `ap-south-1` gets a signature-mismatch error.
2. **R2 rejects ACLs entirely.** `AWS_DEFAULT_ACL = None` and
   `"default_acl": None` are set, so no ACL header is ever sent. Leaving the
   django-storages default of `public-read` produces a confusing 400.
3. **botocore ≥ 1.36 adds a CRC32 checksum to every upload**, which several
   S3-compatible providers reject with an opaque 400. `settings.py` sets
   `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` — but *only* when a custom
   endpoint is configured, so real AWS keeps the stricter default.

### Public vs pre-signed URLs

By default `AWS_QUERYSTRING_AUTH=True`, so images are served as **pre-signed
URLs that expire** after `AWS_QUERYSTRING_EXPIRE` (1 hour). The bucket stays
private and everything works — the SPA just gets a fresh URL each time it loads
a product.

For stable, cacheable, CDN-served URLs instead: R2 bucket → **Settings** →
*Public access* → enable the **r2.dev subdomain** (or attach a custom domain),
then:

```env
AWS_S3_CUSTOM_DOMAIN=pub-<hash>.r2.dev
AWS_QUERYSTRING_AUTH=False
```

Note that `r2.dev` is rate-limited and Cloudflare marks it as
development-only — attach a real custom domain for anything production-ish.

### Other S3-compatible options

| Option | Free tier | `AWS_S3_ENDPOINT_URL` |
| --- | --- | --- |
| **Backblaze B2** | 10 GB | `https://s3.<region>.backblazeb2.com` (region also goes in `AWS_S3_REGION_NAME`, e.g. `us-west-004`) |
| **MinIO** (self-hosted) | free | `http://minio:9000` — add a MinIO service to Compose to test the object-storage path fully offline |
| **Amazon S3** | 5 GB / 12 months | leave `AWS_S3_ENDPOINT_URL` blank; set a real region. IAM policy scoped to `arn:aws:s3:::YOUR-BUCKET/*` with just `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` |

### Verifying it works

```bash
docker compose exec backend python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
name = default_storage.save('healthcheck.txt', ContentFile(b'ok'))
print('wrote:', name)
print('url:  ', default_storage.url(name))
default_storage.delete(name)
print('deleted - round trip OK')
"
```

---

## 5. CD workflow — GitHub secrets and variables

The CI workflow needs **nothing**: `secrets.GITHUB_TOKEN` is injected by GitHub
automatically, and it is what lets the PR comment actions post. Publishing
images to GHCR uses the same token, so the CD build job also needs no setup.

Only the *deploy* step needs configuration, and it skips cleanly when unset.

| Name | Kind | Where to get it |
| --- | --- | --- |
| `RENDER_DEPLOY_HOOK_URL` | secret | Render dashboard → your service → **Settings** → **Deploy Hook** → copy the URL. It already contains its own key, so treat it as a secret |
| `HEALTHCHECK_URL` | variable | Your deployed backend's health endpoint, e.g. `https://opsportal-api.onrender.com/api/health/` |

Add them at **repo → Settings → Secrets and variables → Actions**:

- *Secrets* tab → **New repository secret** → `RENDER_DEPLOY_HOOK_URL`
- *Variables* tab → **New repository variable** → `HEALTHCHECK_URL`

Other hosts, if you are not using Render:

- **Railway** — no deploy hook; use `RAILWAY_TOKEN` (Account Settings → Tokens)
  with `railway up` instead of the curl step.
- **Fly.io** — `fly tokens create deploy` → store as `FLY_API_TOKEN`, then
  `flyctl deploy`.
- **A VPS** — store `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY` and run
  `docker compose pull && docker compose up -d` over SSH.

---

## 6. Files that do not exist yet

| File | Needed when | How to create |
| --- | --- | --- |
| `.secrets` | running `act` | `cp .github/act.secrets.example .secrets` |
| `backend/.env` | running Django **without** Docker | `cp backend/.env.example backend/.env` — works as-is; `DATABASE_URL` blank means SQLite, so there is no database to set up |
| `frontend/.env` | only if the API is on a **different origin** than the SPA | `cp frontend/.env.example frontend/.env`. Leave `VITE_API_BASE_URL` blank for same-origin (correct for Docker *and* the Vite dev proxy) |

All three are gitignored, which is why a fresh clone does not have them.

---

## 7. Absent from `.env`, and fine

These are read by `settings.py` but not listed in `.env`, because the default in
code is already right:

| Variable | Default | Why it is safe to omit |
| --- | --- | --- |
| `DATABASE_URL` | *(empty → SQLite)* | Compose builds it from `POSTGRES_USER/PASSWORD/DB` and passes it to the container directly |
| `CORS_ALLOW_ALL_ORIGINS` | `False` | Should stay false; `CORS_ALLOWED_ORIGINS` is the allowlist |
| `EMAIL_TIMEOUT` | `15` (seconds) | Stops a hung SMTP connection blocking a request |
| `AWS_QUERYSTRING_AUTH` | `True` | Only read when `USE_S3=True` — see §4 |
| `AWS_QUERYSTRING_EXPIRE` | `3600` | Same |
| `TEST_RUNNER` | Django's default | CI overrides it to emit JUnit XML |
| `TEST_OUTPUT_DIR` | `test-results` | Same |

---

## 8. Placeholders to replace before submitting

### Company details — these print on every challan PDF

```env
COMPANY_NAME=Fundsroom Distribution Pvt Ltd
COMPANY_ADDRESS=Unit 4, Trade Centre, Andheri East, Mumbai 400059
COMPANY_GSTIN=27AAPFU0939F1ZV
COMPANY_PHONE=+91 22 4000 1234
COMPANY_EMAIL=accounts@fundsroom.local
```

Invented for the demo — `27AAPFU0939F1ZV` in particular is the sample GSTIN
found in most documentation. Harmless for a case study, but a reviewer opening
the PDF will see it, so swap in something plausible.

### Production secrets

```bash
# SECRET_KEY - a fresh one per deployment, never reused
python -c "import secrets; print(secrets.token_urlsafe(50))"

# POSTGRES_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Production also wants:

```env
DEBUG=False
SECURE_SSL_REDIRECT=True
ALLOWED_HOSTS=your-real-domain.com
CSRF_TRUSTED_ORIGINS=https://your-real-domain.com
FRONTEND_URL=https://your-real-domain.com
```

`FRONTEND_URL` matters more than it looks: emailed password-reset and
verification links are built from it rather than from the request's `Host`
header, so a wrong value produces links pointing at the wrong host. There are
tests covering exactly that (`accounts/tests_email_links.py`).

---

## 9. Verify what is actually loaded

```bash
docker compose exec backend python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.conf import settings as s
print('DEBUG         ', s.DEBUG)
print('DB engine     ', s.DATABASES['default']['ENGINE'])
print('EMAIL_BACKEND ', s.EMAIL_BACKEND)
print('EMAIL_HOST    ', s.EMAIL_HOST, s.EMAIL_PORT, 'TLS' if s.EMAIL_USE_TLS else '')
print('USE_S3        ', s.USE_S3)
print('media storage ', s.STORAGES['default']['BACKEND'])
print('FRONTEND_URL  ', s.FRONTEND_URL)
"
```

Never print `SECRET_KEY`, `EMAIL_HOST_PASSWORD` or `AWS_SECRET_ACCESS_KEY` this
way — the output ends up in shell history and CI logs.

Django's own production audit:

```bash
docker compose exec backend python manage.py check --deploy
```

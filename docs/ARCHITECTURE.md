# Architecture and API reference

## Overview

```
Browser ──HTTPS──> nginx (frontend-component, :443)
                     ├── /api/, /docs, /openapi.json, /health ──> backend-component (FastAPI, :8000)
                     └── /                                     ──> frontend (React build served by nginx, :8001)
backend-component ──> postgres (PostgreSQL 15 + pgvector)
                  ──> AI providers (OVH AI Endpoints, OpenAI, Kiro CLI)
                  ──> SMTP, Stripe/PayPal, OpenStack (Keystone/Nova)
```

- **Backend**: FastAPI application in `app/`, SQLAlchemy 2 models in `app/models/`, Alembic migrations in `migrations/versions/`.
- **Frontend**: React 19 + TypeScript + Vite SPA in `frontend/src/` (pages, components, services, hooks, `i18n/`).
- **Database**: one PostgreSQL database holds both the relational data and the RAG vector table (`md_embeddings`).

## Application lifecycle

On startup (`app/main.py` lifespan), in order:

1. Load the field-encryption key from `DB_ENCRYPTION_KEY` if set (see [SECURITY.md](SECURITY.md#database-field-encryption)).
2. `create_default_admin()` (`app/startup.py`): if the `users` table is empty, create `admin@opcp-psmc.com` / `Admin1234!` (administrator, verified). **Change this password immediately.**
3. `seed_docs_folder()`: publish the files under `docs/to_publish/` into the document space (see [DOCUMENTS.md](DOCUMENTS.md)).
4. Start the APScheduler jobs (`app/scheduler.py`).
5. Warm up the Oracle AI clients and pgvector pool (best effort; never blocks startup).

The backend container runs `alembic upgrade head` before `uvicorn`, so migrations are applied on every start.

### Scheduled jobs

| Job | Schedule | What it does |
|-----|----------|--------------|
| Membership reminders | daily 09:00 | Emails members whose membership is about to expire |
| Event reminders | daily 09:00 | Emails registered users 7 days before an event |
| User deletion | daily 02:00 | Anonymises accounts whose GDPR deletion date has passed |

## Roles

`UserRole` (`app/models/user.py`): `visitor`, `member`, `administrator`. Endpoints use three dependency levels:

- `get_current_user_optional`: anonymous access allowed, result filtered by role.
- `get_current_user` / `get_verified_member`: logged-in user (verified email).
- `get_administrator` / `require_admin`: administrators only.

Login is refused when `membership_status` is `expired` or `suspended`.

## Backend modules

| Module | Prefix | Purpose |
|--------|--------|---------|
| `app/auth` | `/api/auth` | Registration, login, logout (token blacklist), email verification, password reset/change, 2FA (TOTP and email code) |
| `app/users` | `/api/users` | GDPR: personal data export, account deletion request |
| `app/admin` | `/api/admin` | Member management, audit and login logs, activity report, announcements, AI provider toggles, forum and encryption configuration |
| `app/forum` | `/api/forum` | Topics and posts, moderation (hide/delete), public read-only views |
| `app/documents` | `/api/documents` | Document space (upload, list, download, delete) |
| `app/document_adapter` | `/api/document-adapter` | Rewrite a document for an audience with an AI provider, export to PDF/DOCX |
| `app/events` | `/api/events` | Events, registration, cancellation, iCal export |
| `app/tasks` | `/api/tasks` | Task management (private tasks with an owner and assignees) |
| `app/notifications` | `/api/notifications` | Notification preferences |
| `app/info` | `/api/info` | Homepage, legal, board, financial reports, stats (static content from `app/info/config.py`) |
| `app/oracle` | `/api/oracle` | Oracle AI assistant (see [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md)) |
| `app/prerequisites` | `/api/prerequisites` | OPCP installation prerequisites questionnaires |
| `app/payments` | `/api/payments` | Membership payments (see [PAYMENTS.md](PAYMENTS.md)) |
| `app/security` | – | Database field encryption (key derivation, key provider, config) |
| `app/services` | – | Email, storage, document seeding, reminders, payments, invoices, user deletion |
| `app/middleware` | – | Rate limiter (slowapi) |

Top-level endpoints: `GET /health`, `GET /` and the OpenAPI UI at `/docs` (`/openapi.json`).

## API reference

The interactive reference is at `/docs`. Summary:

### `/api/auth`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/register` | 10/hour per IP. Sends a verification email (24 h link) |
| POST | `/login` | 20/hour per IP + 5 failures per 15 min per email. Returns a JWT, or a 2FA challenge |
| POST | `/login/2fa` | Completes login with the TOTP or email code (challenge valid 5 min) |
| POST | `/logout` | Blacklists the current token |
| POST/GET | `/verify-email` | Email verification |
| POST | `/password-reset`, `/password-reset/confirm` | Reset link valid 1 hour |
| POST | `/change-password` | Logged-in user |
| GET | `/2fa/status` | |
| POST | `/2fa/totp/setup`, `/2fa/totp/confirm`, `/2fa/totp/disable` | TOTP (authenticator app) |
| POST | `/2fa/email/enable`, `/2fa/email/disable` | Email-code 2FA |

### `/api/admin` (administrators)

| Method | Path |
|--------|------|
| GET | `/members` |
| PUT | `/members/{id}/role`, `/members/{id}/membership-status`, `/members/{id}/email-verification`, `/members/{id}/deactivate` |
| GET | `/audit-log`, `/login-logs`, `/reports/activity` |
| POST | `/announcements` |
| GET/PUT | `/ai-providers`, `/forum-config`, `/encryption-config` |

### `/api/forum`

| Method | Path | Access |
|--------|------|--------|
| GET | `/config` | public |
| GET | `/topics/public`, `/topics/{id}/public`, `/topics/{id}/publichtml` | public (read-only, HTML view for sharing) |
| GET/POST | `/topics`, `/topics/{id}`, `/topics/{id}/posts` | verified members |
| PUT | `/posts/{id}` | author |
| PUT/DELETE | `/posts/{id}/hide`, `/posts/{id}` | administrators |

### `/api/events` and `/api/tasks`

| Method | Path | Access |
|--------|------|--------|
| GET | `/api/events` | logged-in users |
| POST, PUT | `/api/events`, `/api/events/{id}`, `/api/events/{id}/cancel` | administrators |
| POST/DELETE | `/api/events/{id}/register` | logged-in users |
| GET | `/api/events/export/ical` | logged-in users |
| GET, POST | `/api/tasks` | logged-in users |
| PUT | `/api/tasks/{id}`, `/api/tasks/{id}/cancel` | logged-in users (owner, assignees or administrators) |

A task has one owner (the creator by default) and optional assignees. Tasks are private: only the owner, the assignees and administrators can see them. Events, by contrast, are visible to all members when they have no assignees.

### `/api/prerequisites`

Each OPCP **installation** (customer project) has its own set of prerequisite pages, identified by a `slug`. Static content is edited by administrators; client answers are shared by all users of the installation (last write wins).

| Method | Path | Access |
|--------|------|--------|
| GET, POST | `/installations` | list: users; create: administrators |
| PUT, DELETE | `/installations/{id}` | administrators |
| GET, PUT | `/installations/{id}/{slug}/content` | read: users; write: administrators |
| GET, PUT | `/installations/{id}/{slug}/answers[/{row_id}]` | users |
| GET, PUT | `/installations/{id}/servers-nodes/credentials` | OpenStack application credential (secret is write-only, stored encrypted) |
| POST | `/installations/{id}/servers-nodes/servers/retrieve` | Lists Nova servers live through Keystone, optionally via `OPENSTACK_HTTPS_PROXY` |
| GET, PUT | `/installations/{id}/servers-nodes/nodes` | Server/node role overrides |

### Other routers

- `/api/users`: `GET /me/export`, `DELETE /me` (see [SECURITY.md](SECURITY.md#gdpr)).
- `/api/notifications`: `GET/PUT /preferences`.
- `/api/info`: `GET /homepage`, `/legal`, `/board`, `/financial-reports`, `/stats`.
- `/api/documents`, `/api/document-adapter`: see [DOCUMENTS.md](DOCUMENTS.md).
- `/api/oracle`: see [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md).
- `/api/payments`: see [PAYMENTS.md](PAYMENTS.md).

## Data model

| Table | Model |
|-------|-------|
| `users`, `token_blacklist`, `user_deletion*` | `user.py`, `token_blacklist.py`, `user_deletion.py` |
| `audit_log` | `audit.py` |
| `forum_topics`, `forum_posts`, `forum_config` | `forum.py`, `forum_config.py` |
| `documents` | `document.py` |
| `events`, `event_registrations`, `event_assignments` | `event.py` |
| `tasks` | `task.py` |
| `notifications`, `notification_preferences` | `notification.py` |
| `payments` | `payment.py` |
| `oracle_queries`, `ai_provider_config` | `oracle.py`, `ai_provider_config.py` |
| `installations`, `prerequisite_content`, `prerequisite_answers`, `prerequisite_server_node`, `prerequisite_credential_config` | `installation.py`, `prerequisite.py`, `credential_config.py` |
| `encryption_config` | `encryption_config.py` |
| `md_embeddings` (RAG vectors, created on demand, not managed by Alembic) | `app/oracle/ai_providers.py` |

## Frontend

Routes (`frontend/src/App.tsx`); all except the auth pages require login:

| Route | Page |
|-------|------|
| `/login`, `/register`, `/forgot-password`, `/reset-password` | Authentication |
| `/` | Home (announcements, public forum topics) |
| `/forum`, `/forum/new`, `/forum/topics/:topicId` | Forum |
| `/documents` | Document space |
| `/document-adapter` | Document adapter |
| `/oracle` | Oracle AI chat |
| `/events`, `/tasks` | Events and tasks |
| `/prerequisites/how-to-use`, `/prerequisites/installations`, `/prerequisites/installations/:installationId/:slug` | Prerequisites |
| `/account/security` | Password and 2FA |
| `/admin/users`, `/admin/events`, `/admin/tasks`, `/admin/configuration` | Administration |

The UI is translated through `frontend/src/i18n/translations.ts`. The app can be served under a sub-path: `VITE_BASE_PATH` (build time) sets the router base, and `VITE_API_BASE_URL` overrides the API base (default `<base>/api`).

# OPCP workspace

Member web platform for the OPCP workspace. It provides a forum, a document space, events and tasks, OPCP installation prerequisites, and an AI assistant (the Oracle) with an OPCP RAG companion. The stack is a FastAPI backend, a React/Vite frontend and PostgreSQL with pgvector, deployed with Docker Compose behind nginx.

## Features

- **Accounts**: registration with email verification, password reset, 2FA (TOTP or email code), roles (visitor, member, administrator), membership status
- **Forum**: topics and posts, admin moderation, public read-only views
- **Documents**: document space with access levels; files in `docs/to_publish/` are published automatically
- **Document adapter**: rewrites a PDF/Word document for a target audience with AI, then exports it to PDF or DOCX
- **Oracle AI**: chat assistant with streamed answers. Providers: Shai (OVH AI Endpoints), OPCP Companion (RAG over pgvector), OpenAI, Kiro CLI
- **Prerequisites**: per-installation OPCP prerequisite questionnaires, with live OpenStack server retrieval
- **Events and tasks**: event registration with iCal export and email reminders; private tasks with assignees
- **Administration**: member management, audit and login logs, activity report, announcements, AI provider toggles, forum and encryption settings
- **Compliance and security**: GDPR data export and deletion, rate limiting, optional database field encryption
- **Operations**: local and S3/OVH database backups and restore scripts
- **Payments** (backend only): Stripe and PayPal membership payments with PDF invoices

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, APScheduler, slowapi |
| Database | PostgreSQL 15 with pgvector (`pgvector/pgvector:pg15`) |
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS, react-router |
| AI | OVH AI Endpoints (OpenAI-compatible), OpenAI, Kiro CLI |
| Tests | pytest + Hypothesis (backend); Vitest + Testing Library + fast-check (frontend) |
| Infrastructure | Docker Compose, nginx (TLS reverse proxy) |

## Quick start

### Docker (recommended)

```bash
git submodule update --init         # deployApp.sh lives in the ai-swautomorph--shared submodule
cp .env.example .env                 # set SECRET_KEY, SMTP_*, SHAI_API_KEY, ...
./deployApp.sh start <USER_ID>
```

The application is served at `https://<DOMAIN>:<HTTPS_PORT>`, where `HTTPS_PORT = 6024 + 100 × USER_ID`. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for ports, TLS and a plain `docker compose up` alternative.

On an empty database, the default administrator is `admin@opcp-psmc.com` / `Admin1234!`. Change the password right away.

To build the RAG index for the OPCP Companion:

```bash
docker compose --profile ingest run --rm ingest
```

### Local development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # DATABASE_URL must point to a PostgreSQL with pgvector
alembic upgrade head
uvicorn app.main:app --reload        # API on :8000, OpenAPI UI at /docs

cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000/api npm run dev   # UI on :3000
```

## Configuration

All settings come from environment variables or `.env` (`app/config.py`). The main ones:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | JWT signing key (required) |
| `DATABASE_URL` | PostgreSQL connection |
| `ALLOWED_ORIGINS` | CORS origins |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Outgoing email |
| `SHAI_API_KEY`, `SHAI_API_URL`, `SHAI_MODEL` | Default AI provider |
| `OVH_AI_ENDPOINT`, `OVH_AI_TOKEN`, `LLM_*`, `EMBEDDING_*` | OPCP Companion (RAG) |
| `DB_ENCRYPTION_KEY` | Optional field-encryption key |
| `KEY_DECRYPT_INFORMATIONS_OPCP` | Decrypts the OPCP reference docs in `docs/opcp_external_docs` (stored encrypted) |

Full list: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Project structure

```
opcp-workspace/
├── app/                      # FastAPI backend
│   ├── admin/ auth/ users/   # Administration, authentication/2FA, GDPR endpoints
│   ├── forum/ documents/ events/ tasks/ notifications/ info/
│   ├── document_adapter/     # AI audience adaptation + PDF/DOCX export
│   ├── oracle/               # Oracle AI providers, RAG, streaming
│   ├── prerequisites/        # Installation prerequisites + OpenStack proxy
│   ├── payments/             # Stripe/PayPal endpoints
│   ├── security/             # Database field encryption
│   ├── services/             # Email, storage, document seeding, reminders, payments
│   ├── middleware/           # Rate limiting
│   ├── models/               # SQLAlchemy models
│   ├── main.py               # App, routers, startup lifecycle
│   ├── config.py             # Settings
│   └── scheduler.py          # Daily jobs
├── frontend/                 # React/Vite/TypeScript SPA (src/pages, components, services, i18n)
├── migrations/               # Alembic migrations
├── tests/                    # Backend tests (pytest)
├── scripts/                  # Backup/restore, RAG ingestion, encryption migration, DB access
├── conf/                     # deploy.ini, nginx.conf.template, shai_context.md (Shai business context)
├── docs/                     # Documentation + content folders (to_publish/, opcp_external_docs/)
├── ai-swautomorph--shared/   # Submodule: shared deployment tooling (deployApp.sh)
├── shared/                   # Submodule: shared Kiro specs
├── Dockerfile                # Backend image
└── docker-compose.yml        # postgres, backend-component, frontend, frontend-component (nginx), ingest
```

## Testing

```bash
# Backend (uses a SQLite file, ./test.db; no PostgreSQL needed)
pytest
pytest -m property        # Hypothesis property tests (also: -m unit, -m integration)
pytest --cov=app --cov-report=html

# Frontend
cd frontend
npm test                  # vitest run
npm run lint
npm run build             # type-check + production build
```

## Documentation

| Document | Content |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, lifecycle, roles, API reference, data model, frontend routes |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker Compose, `deployApp.sh`, ports, TLS, nginx, migrations |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Database access, backups, restore, admin recovery |
| [docs/SECURITY.md](docs/SECURITY.md) | Authentication, 2FA, rate limits, GDPR, field encryption |
| [docs/ORACLE_AI_MODULE.md](docs/ORACLE_AI_MODULE.md) | Oracle AI providers, RAG companion, ingestion |
| [docs/DOCUMENTS.md](docs/DOCUMENTS.md) | Document space and document adapter |
| [docs/PAYMENTS.md](docs/PAYMENTS.md) | Membership payments |
| [scripts/README.md](scripts/README.md) | Script reference |

## License

Copyright © 2026 OPCP workspace PSMC

# OPCP workspace

Member web platform for the OPCP workspace: forum, documents, events, tasks, notifications and the OPCP RAG AI companion. It consists of a FastAPI backend and a React/Vite frontend.

## Features

- Member authentication with two-factor authentication (TOTP and email) and password reset
- Discussion forum with moderation and public access
- Secure document space, plus a document adapter (Word/PDF extraction and export)
- Event planning with registration, reminders and iCal export
- Task management
- Notifications (email and server-sent events)
- Administration and role management, with an audit log
- Prerequisites questionnaire and information pages
- GDPR compliance (user data export and deletion)
- Rate limiting on the API
- Oracle AI module (RAG over documents stored in PostgreSQL with pgvector)
- Database backups to S3-compatible storage (including OVH) and restore scripts
- Optional application-level database field encryption (see below)

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI, SQLAlchemy, Alembic, APScheduler
- **Database**: PostgreSQL (pgvector image `pgvector/pgvector:pg15` in Docker Compose)
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, react-router
- **Testing**: pytest, hypothesis (backend); Vitest, Testing Library, fast-check (frontend)
- **Infrastructure**: Docker, Docker Compose, nginx

## Setup

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- pip and virtualenv
- Node.js and npm (for the frontend)
- Docker and Docker Compose (optional, for the containerised deployment)

### Backend installation (manual)

1. Clone the repository:
```bash
git clone <repository-url>
cd opcp-workspace
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

`.env.example` documents the `PG_*` and `TABLE_NAME` settings (pgvector connection), the `SHAI_API_KEY`, `SHAI_API_URL` and `SHAI_MODEL` settings (Oracle AI provider) and the optional `DB_ENCRYPTION_KEY`. Replace the placeholder values in your own `.env` and never commit it.

5. Setup PostgreSQL database:
```bash
# Create database and user
createdb OPCP_db
createuser OPCP_user
# Grant privileges (run in psql)
GRANT ALL PRIVILEGES ON DATABASE OPCP_db TO OPCP_user;
```

6. Run database migrations:
```bash
alembic upgrade head
```

7. Start the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at http://opcp-workspace:8000

API documentation: http://opcp-workspace:8000/docs

> The manual flow above uses the `OPCP_db` / `OPCP_user` database. The Docker Compose deployment is independent and provisions its own `shai_db` / `shai_user` database inside the `postgres` container.

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite development server
npm run build    # Type-check and production build
npm run lint     # ESLint
npm run preview  # Preview the production build
```

### Docker Compose

`docker-compose.yml` defines these services:

| Service | Description |
|---------|-------------|
| `postgres` | PostgreSQL with pgvector (`pgvector/pgvector:pg15`), data in the `postgres_data` volume |
| `backend-component` | FastAPI API (container port 8000), storage in the `app_data` volume |
| `frontend` | Built React frontend |
| `frontend-component` | nginx reverse proxy with SSL (certificates are read from an `ssl` directory you provide at the repo root, mounted by `docker-compose.yml`) |
| `ingest` | One-off RAG document ingestion (`python -m scripts.ingest_embeddings`), only started with the `ingest` profile |

```bash
# Start the stack
docker compose up -d --build

# Run the one-off ingestion job
docker compose --profile ingest run --rm ingest
```

Compose reads its settings from `.env` (copied from `.env.example`).

### Helper scripts

| Script | Purpose |
|--------|---------|
| `setup.sh` | Initial setup of the workspace |
| `scripts/start.sh` | Start the application |
| `scripts/stop.sh` | Stop the application |
| `scripts/restart.sh` | Restart the application |
| `scripts/deploy.sh` | Deploy the application |
| `scripts/backup.sh` | Back up the database |

### Backup and restore

Database backup and restore (local and S3/OVH) are covered in `scripts/README.md` and `scripts/README_BACKUP.md`. See also `docs/BACKUP_S3_SETUP.md` and `docs/RESTORE_COMMANDS.md`.

## Project Structure

```
opcp-workspace/
├── app/                    # Backend application code (FastAPI)
│   ├── admin/              # Administration and roles
│   ├── auth/               # Authentication and 2FA
│   ├── document_adapter/   # Document audience adapter (Word/PDF)
│   ├── documents/          # Document space
│   ├── events/             # Events, registration, iCal
│   ├── forum/              # Discussion forum
│   ├── info/               # Information pages
│   ├── middleware/         # HTTP middleware
│   ├── models/             # SQLAlchemy models
│   ├── notifications/      # Email and SSE notifications
│   ├── oracle/             # Oracle AI module (RAG)
│   ├── payments/           # Stripe and PayPal payments
│   ├── prerequisites/      # Prerequisites questionnaire
│   ├── security/           # Security helpers (incl. field encryption)
│   ├── services/           # Shared services
│   ├── tasks/              # Task management
│   ├── users/              # Member management
│   ├── config.py           # Configuration
│   ├── database.py         # Database setup
│   ├── error_handlers.py   # Exception handlers
│   ├── exceptions.py       # Custom exceptions
│   ├── logging_config.py   # Logging configuration
│   ├── main.py             # FastAPI application
│   ├── scheduler.py        # Background jobs (APScheduler)
│   └── startup.py          # Startup tasks
├── frontend/               # React/Vite/TypeScript frontend
│   ├── src/                # Pages, components, hooks, services, i18n, tests
│   ├── public/             # Static assets
│   └── package.json        # npm scripts and dependencies
├── shared/                 # Git submodule (shared content)
├── tests/                  # Backend tests (pytest)
│   ├── prerequisites/      # Prerequisites tests
│   └── conftest.py         # Pytest fixtures
├── migrations/             # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/           # Migration files
├── scripts/                # Start/stop, deploy, backup/restore, ingestion, encryption
├── docs/                   # Feature and operations documentation
├── conf/                   # Deployment and Oracle context configuration
├── static/                 # Static files
├── templates/              # Email templates
├── storage/                # File storage
├── Dockerfile              # Backend image
├── docker-compose.yml      # Docker Compose stack
├── requirements.txt        # Python dependencies
├── alembic.ini             # Alembic configuration
├── pytest.ini              # Pytest configuration
├── setup.sh                # Initial setup script
├── SETUP.md                # Initial setup notes
├── .env.example            # Example environment variables
└── README.md               # This file
```

## Testing

### Backend

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

Run property-based tests:
```bash
pytest -m property
```

`pytest.ini` registers the `property`, `unit` and `integration` markers (strict markers are enabled), so you can also run `pytest -m unit` or `pytest -m integration`. Tests live in `tests/` as `test_*.py` files, with `tests/prerequisites/` for the prerequisites module.

### Frontend

```bash
cd frontend
npm test       # Vitest (vitest run)
npm run lint   # ESLint
```

Frontend tests are `*.test.tsx` files under `frontend/src`.

## Documentation

- [SETUP.md](SETUP.md): initial setup notes
- [scripts/README.md](scripts/README.md): scripts, backup/restore and encryption workflow
- [scripts/README_BACKUP.md](scripts/README_BACKUP.md): backup guide
- [docs/QUICK_START.md](docs/QUICK_START.md): quick start
- [docs/OPCP_First_Steps.md](docs/OPCP_First_Steps.md): first steps
- [docs/ORACLE_AI_MODULE.md](docs/ORACLE_AI_MODULE.md): Oracle AI module
- [docs/STRIPE_INTEGRATION.md](docs/STRIPE_INTEGRATION.md): Stripe integration
- [docs/PAYPAL_INTEGRATION.md](docs/PAYPAL_INTEGRATION.md): PayPal integration
- [docs/SMTP_CONFIGURATION.md](docs/SMTP_CONFIGURATION.md): SMTP configuration
- [docs/BACKUP_S3_SETUP.md](docs/BACKUP_S3_SETUP.md): S3 backup setup

## Development

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migration:
```bash
alembic downgrade -1
```

### Code Style

This project follows PEP 8 style guidelines.

## Database Field Encryption (optional)

Application-level, opt-in encryption of a small set of sensitive non-indexed
free-text columns (`forum_topics.title`, `forum_posts.content`,
`users.first_name`, `users.last_name`, `notifications.content`,
`events.description`, `tasks.description`). Disabled by default — data is stored
in plaintext until an administrator opts in.

How it works:
- An administrator enables the toggle and sets a password key on the admin
  **Configuration** page. The key is never stored; only a salted PBKDF2
  verification hash is persisted, so the app can validate the key but cannot
  recover it. The Fernet encryption key is derived from the password key.
- Changing the state of existing data is applied by the offline script
  `scripts/migrate_encryption.py` (`--enable` / `--disable`), which
  encrypts/decrypts all in-scope rows and only then flips
  `encryption_config.enabled`.
- Set `DB_ENCRYPTION_KEY` (see `.env.example`) to let the app decrypt after a
  restart without re-entering the key.

> ⚠️ If encryption is enabled and the password key (and the derived
> `DB_ENCRYPTION_KEY`) are lost, the encrypted data is **permanently
> unrecoverable** by design.

See `scripts/README.md` for the full workflow.

## License

Copyright © 2026 OPCP workspace PSMC

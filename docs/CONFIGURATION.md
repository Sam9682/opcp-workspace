# Configuration

The backend reads its settings from environment variables and from `.env` (`app/config.py`, pydantic-settings, case-sensitive). Start from the template:

```bash
cp .env.example .env
```

Never commit `.env` or `.env.prod`.

In Docker Compose:

- every service loads `.env` (`env_file`);
- `docker-compose.yml` forces `DATABASE_URL`, `SECRET_KEY`, `DOMAIN`, `API_URL` and `SSL_EMAIL` on the backend from the shell/`--env-file` environment;
- the PostgreSQL service always uses database `shai_db` and user `shai_user`, with password `POSTGRES_PASSWORD` (default `shai_password`).

## Backend settings

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://shai_user:shai_password@postgres:5432/shai_db` | SQLAlchemy connection string |
| `SECRET_KEY` | **required** | JWT signing key. It is also used to derive the key that encrypts stored OpenStack credentials, so changing it makes those credentials unreadable |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Session lifetime |
| `APP_NAME` / `APP_VERSION` | `AI-SHAI` / `1.0.0` | Shown by `/health` and the OpenAPI page |
| `DEBUG` | `false` | |
| `ALLOWED_ORIGINS` | `https://opcp-psmc.com` | Comma-separated CORS origins |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `UPLOAD_DIR` | `./storage/uploads` | Uploaded files and generated invoices |
| `MAX_UPLOAD_SIZE` | `10485760` | Upload limit in bytes (10 MB) |
| `DOCS_SEED_DIR` | `./docs/to_publish` | Folder published into the document space at startup (see [DOCUMENTS.md](DOCUMENTS.md)) |

### Email (SMTP)

| Variable | Default |
|----------|---------|
| `SMTP_HOST` | `localhost` |
| `SMTP_PORT` | `587` (STARTTLS) |
| `SMTP_USER` | empty |
| `SMTP_PASSWORD` | empty |
| `SMTP_FROM` | `noreply@opcp-psmc.com` |

Authentication emails (verification, password reset, 2FA codes) are **silently skipped** when `SMTP_PASSWORD` is empty. To test the configuration:

```bash
python -m app.test_smtp          # or: docker exec -it <backend-container> python -m app.test_smtp
```

### AI providers

See [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md).

| Variable | Default | Used by |
|----------|---------|---------|
| `SHAI_API_KEY` | empty (required for Shai) | `shai` |
| `SHAI_API_URL` | `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` | `shai` |
| `SHAI_MODEL` | `Qwen2.5-Coder-32B-Instruct` | `shai` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | empty / `gpt-4` | `openai` |
| `OVH_AI_ENDPOINT` / `OVH_AI_TOKEN` | empty | `opcp_companion` embeddings, ingestion |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `Qwen3-Embedding-8B` / `4096` | `opcp_companion` |
| `LLM_ENDPOINT` / `LLM_TOKEN` | fall back to `OVH_AI_*` | `opcp_companion` generation |
| `LLM_MODEL` | `Qwen3-Embedding-8B` (set it to a chat model) | `opcp_companion` generation |
| `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD` | derived from `DATABASE_URL` | pgvector pool |
| `TABLE_NAME` | `md_embeddings` | pgvector table |

### Payments

| Variable | Default |
|----------|---------|
| `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` | dummy test values |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | dummy values |
| `PAYPAL_MODE` | `sandbox` |
| `ANNUAL_MEMBERSHIP_FEE` | `50.00` |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_ENCRYPTION_KEY` | empty | Fernet key that unlocks field encryption at startup (see [SECURITY.md](SECURITY.md#database-field-encryption)) |
| `KEY_DECRYPT_INFORMATIONS_OPCP` | `!!!ENTER_THE_KEY_HERE` in `.env.example` (means "no key") | Passphrase that decrypts the OPCP reference documentation in `docs/opcp_external_docs` (see [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md#encrypted-opcp-reference-documentation)) |
| `OPENSTACK_HTTPS_PROXY` | empty | Forward proxy for OpenStack calls from the prerequisites module. Also read from `https_proxy`, `http_proxy`, `HTTPS_PROXY` or `HTTP_PROXY` |

## Deployment variables

Used by `docker-compose.yml` and `deployApp.sh` (see [DEPLOYMENT.md](DEPLOYMENT.md)):

| Variable | Description |
|----------|-------------|
| `USER_ID` | Deployment number. It makes container and network names unique and selects the port range |
| `HTTPS_PORT` | Host port of nginx (443) |
| `HTTP_PORT` | Host port of the frontend container (8001) |
| `HTTP_PORT2` | Host port of the backend (8000) |
| `HTTPS_PORT2` | Host port of PostgreSQL (5432) |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `DOMAIN`, `SSL_EMAIL`, `API_URL` | Passed to the backend container; `DOMAIN` is also used for certificates |

## Frontend build variables

| Variable | Description |
|----------|-------------|
| `VITE_BASE_PATH` | Mount path of the SPA (default: Vite `base`, `/`) |
| `VITE_API_BASE_URL` | API base URL (default `<base path>/api`) |

These are read at build time; `frontend/Dockerfile` does not pass any, so the Docker build uses the defaults.

## Script variables

| Variable | Used by |
|----------|---------|
| `OVH_S3_ENDPOINT` (default `https://s3.gra.io.cloud.ovh.net`), `OVH_S3_REGION` (`gra`), `OVH_S3_ACCESS_KEY`, `OVH_S3_SECRET_KEY` | `scripts/backup_database_universal.py`, `scripts/restore_from_s3_universal.py` with `--s3-provider/--provider ovh` |
| AWS credential chain (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`…) | S3 scripts in AWS mode |
| `DB_ENCRYPTION_PASSWORD` | `scripts/migrate_encryption.py` (prompted when unset) |
| `KEY_DECRYPT_INFORMATIONS_OPCP` | `scripts/opcp_docs_crypto.py` (prompted when unset) |

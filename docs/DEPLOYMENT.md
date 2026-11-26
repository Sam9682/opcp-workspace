# Deployment

## Docker Compose stack

| Service | Image | Container port | Host port variable |
|---------|-------|----------------|--------------------|
| `postgres` | `pgvector/pgvector:pg15` (db `shai_db`, user `shai_user`, volume `postgres_data`) | 5432 | `HTTPS_PORT2` |
| `backend-component` | root `Dockerfile` (python:3.11-slim, Kiro CLI, uvicorn) | 8000 | `HTTP_PORT2` |
| `frontend` | `frontend/Dockerfile` (Vite build served by nginx) | 8001 | `HTTP_PORT` |
| `frontend-component` | `nginx:alpine` reverse proxy with TLS | 443 | `HTTPS_PORT` |
| `ingest` | root `Dockerfile`, profile `ingest` only | – | – |

Backend container:

- mounts the `app_data` volume at `/app/storage` (uploads, invoices);
- mounts `./ssl` and `./conf/shai_context.md` read-only. `docs/opcp_external_docs` is deliberately not mounted: the backend decrypts the image's copy at startup (see [ORACLE_AI_MODULE.md](ORACLE_AI_MODULE.md#encrypted-opcp-reference-documentation));
- runs `alembic upgrade head` and then `uvicorn` on every start.

The whole repository (including `docs/to_publish/`) is copied into the image, and there is no `.dockerignore`.

Each deployment gets its own Docker network, `opcp-workspace-network-${USER_ID}`. This prevents nginx from resolving `frontend` or `backend-component` to containers of another deployment on the same host.

### Manual start

```bash
cp .env.example .env              # then edit
mkdir -p ssl                      # put fullchain.pem and privkey.pem here
cp conf/nginx.conf.template conf/nginx.conf
docker compose up -d --build
docker compose --profile ingest run --rm ingest   # optional: build the RAG index
```

## deployApp.sh

`deployApp.sh` is a symlink to `ai-swautomorph--shared/deployApp.sh` (git submodule). Initialise the submodules first:

```bash
git submodule update --init
```

Usage (as a non-root user with Docker and docker-compose v1):

```bash
./deployApp.sh start   [USER_ID] [USER_NAME] [USER_EMAIL] [DESCRIPTION]
./deployApp.sh stop    [USER_ID]
./deployApp.sh restart [USER_ID]
./deployApp.sh logs    [USER_ID]
./deployApp.sh ps      [USER_ID]   # JSON status (needs jq)
./deployApp.sh help
```

`conf/deploy.ini` provides `NAME_OF_APPLICATION=opcp-workspace` and `APPLICATION_IDENTITY_NUMBER=2`. `DOMAIN` (default `softfluid.fr`) and `EMAIL` can be overridden from the environment.

### Ports

The base port is `6000 + 100 × USER_ID + 12 × APPLICATION_IDENTITY_NUMBER`, so `6024 + 100 × USER_ID` for this application. Ports are assigned in this order:

| Offset | Variable | Service |
|--------|----------|---------|
| +0 | `HTTPS_PORT` | nginx (public HTTPS entry point) |
| +1 | `HTTP_PORT` | frontend container |
| +4 | `HTTPS_PORT2` | PostgreSQL |
| +5 | `HTTP_PORT2` | backend API |

The other offsets (+2, +3, +6…+11) are reserved. Example: `USER_ID=34` gives `HTTPS_PORT=9424`.

### What `start` does

1. Checks prerequisites. If `.env.prod` is missing, generates it (random `POSTGRES_PASSWORD`, `DATABASE_URL`, `DOMAIN`…; chmod 600). Compose uses it only through `--env-file`, for variable interpolation. The containers still read `.env`, so put application settings (`SECRET_KEY`, SMTP, AI keys…) in `.env`.
2. Copies `conf/nginx.conf.template` to `conf/nginx.conf`.
3. Sets up TLS in `./ssl/fullchain.pem` and `./ssl/privkey.pem`. It tries, in order: existing files, `~/.ssh/fullchain_domain.crt` + `~/.ssh/privateKey_domain.key`, `ssl/fullchain_domain.crt` + `ssl/privateKey_domain.key`, certbot standalone, and finally a self-signed certificate.
4. Runs `docker-compose down`, then `build --no-cache`, then `up -d`, under project name `opcp-workspace-<USER_ID>-<HTTPS_PORT>`.
5. Checks `https://$DOMAIN:$HTTPS_PORT/`, opens the ports with `ufw` if it is installed, and regenerates `scripts/backup.sh` (see [OPERATIONS.md](OPERATIONS.md#backups)).

## nginx

`conf/nginx.conf.template` is a single TLS server (port 443, TLSv1.2/1.3) with:

- `client_max_body_size 100M`;
- 600 s proxy timeouts, needed for long AI calls;
- `/api/` proxied to the backend, with CORS headers and `OPTIONS` answered with 204;
- `/docs`, `/openapi.json` and `/health` proxied to the backend;
- `/` proxied to the frontend container, whose own nginx (`frontend/nginx.conf`) serves the SPA with an `index.html` fallback.

## First login

On an empty database the backend creates `admin@opcp-psmc.com` / `Admin1234!`. Log in, change the password on **Account → Security**, and enable 2FA.

## Local development (without Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # point DATABASE_URL at a PostgreSQL with the pgvector extension
alembic upgrade head
uvicorn app.main:app --reload # http://localhost:8000, docs at /docs

cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000/api npm run dev   # http://localhost:3000
```

The Vite dev server has no `/api` proxy, so point the frontend at the backend with `VITE_API_BASE_URL` and add `http://localhost:3000` to `ALLOWED_ORIGINS` in `.env`.

## Migrations

```bash
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

Migrations live in `migrations/versions/`. In Docker, they are applied automatically when the backend starts.

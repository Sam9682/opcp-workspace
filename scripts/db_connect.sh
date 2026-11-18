#!/bin/bash
# Helper script to connect to the PostgreSQL database
# This prevents "role root does not exist" errors

set -e

# Run from the project root so .env and docker-compose.yml are found
cd "$(dirname "$0")/.."

# Load a variable from .env only if it is not already set in the environment
load_env_var() {
    local name="$1" line value
    if [ -n "${!name}" ]; then
        return
    fi
    [ -f .env ] || return 0
    line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${name}=" .env | tail -n 1) || true
    [ -n "$line" ] || return 0
    value="${line#*=}"
    # Strip surrounding quotes
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    export "$name=$value"
}

if [ ! -f .env ]; then
    echo "⚠️  .env file not found, using environment variables only"
fi

for v in PG_USER PG_PASSWORD PG_HOST PG_PORT PG_DB DATABASE_URL; do
    load_env_var "$v"
done

# Connection details: PG_* variables (environment first, then .env).
# Missing ones fall back to DATABASE_URL (postgresql://user:password@host:port/database).
DB_USER="$PG_USER"
DB_PASS="$PG_PASSWORD"
DB_HOST="$PG_HOST"
DB_PORT="$PG_PORT"
DB_NAME="$PG_DB"

if [ -n "$DATABASE_URL" ]; then
    DB_USER=${DB_USER:-$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')}
    DB_PASS=${DB_PASS:-$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')}
    DB_HOST=${DB_HOST:-$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:\/]*\)[:\/].*/\1/p')}
    DB_PORT=${DB_PORT:-$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')}
    DB_NAME=${DB_NAME:-$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')}
fi

if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
    echo "❌ Error: set PG_USER and PG_DB (or DATABASE_URL) in the environment or .env"
    exit 1
fi

echo "🔌 Connecting to PostgreSQL database..."
echo "   Host: $DB_HOST:$DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo ""

# The compose project is deployed under a custom name (e.g. opcp-workspace-1-6124),
# so `docker-compose exec` from this directory cannot find the service.
# Locate the running postgres container by its compose labels (working dir + service).
[ -t 0 ] && TTY_FLAG=1
PROJECT_DIR="$(pwd)"
CONTAINER=$(docker ps -q \
    --filter "label=com.docker.compose.project.working_dir=$PROJECT_DIR" \
    --filter "label=com.docker.compose.service=postgres" | head -n 1)

# Fallback: container name from docker-compose.yml (opcp-workspace-postgres-<USER_ID>-5432)
if [ -z "$CONTAINER" ]; then
    CONTAINER=$(docker ps -q --filter "name=^opcp-workspace-postgres-${USER_ID:-1}-5432$" | head -n 1)
fi

if [ -n "$CONTAINER" ]; then
    docker exec -i${TTY_FLAG:+t} -e PGPASSWORD="$DB_PASS" "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"
else
    # Last resort: default compose project
    docker-compose exec -e PGPASSWORD="$DB_PASS" postgres psql -U "$DB_USER" -d "$DB_NAME"
fi
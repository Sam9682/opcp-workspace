#!/bin/bash
# Script to diagnose and fix login issues.
# Connects to the PostgreSQL docker instance the same way as scripts/db_connect.sh
# and sets/modifies the password of admin@opcp-psmc.com in the "users" table.

# Run from the project root so .env and docker-compose.yml are found
cd "$(dirname "$0")/.." || exit 1

ADMIN_EMAIL="admin@opcp-psmc.com"

# ---------------------------------------------------------------------------
# Database connection (same logic as scripts/db_connect.sh)
# ---------------------------------------------------------------------------
load_env_var() {
    local name="$1" line value
    if [ -n "${!name}" ]; then
        return
    fi
    [ -f .env ] || return 0
    line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${name}=" .env | tail -n 1) || true
    [ -n "$line" ] || return 0
    value="${line#*=}"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    export "$name=$value"
}

for v in PG_USER PG_PASSWORD PG_HOST PG_PORT PG_DB DATABASE_URL; do
    load_env_var "$v"
done

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

# Locate the running postgres container by its compose labels (working dir + service),
# falling back to the container name from docker-compose.yml.
PROJECT_DIR="$(pwd)"
CONTAINER=$(docker ps -q \
    --filter "label=com.docker.compose.project.working_dir=$PROJECT_DIR" \
    --filter "label=com.docker.compose.service=postgres" | head -n 1)
if [ -z "$CONTAINER" ]; then
    CONTAINER=$(docker ps -q --filter "name=^opcp-workspace-postgres-${USER_ID:-1}-5432$" | head -n 1)
fi

# Run psql inside the postgres container. SQL is read from stdin; extra args are passed to psql.
run_psql() {
    if [ -n "$CONTAINER" ]; then
        docker exec -i -e PGPASSWORD="$DB_PASS" "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" "$@"
    else
        docker-compose exec -T -e PGPASSWORD="$DB_PASS" postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" "$@"
    fi
}

# bcrypt-hash the password read from stdin (same algorithm as app/auth/password.py).
# Tries the host python first, then the running backend container.
# Returns 1 if neither has bcrypt (the caller then falls back to pgcrypto in postgres).
hash_password() {
    local code='import sys,bcrypt; pw=sys.stdin.buffer.read().rstrip(b"\n"); print(bcrypt.hashpw(pw, bcrypt.gensalt()).decode())'
    local pw="$1" out backend
    if out=$(printf '%s' "$pw" | python3 -c "$code" 2>/dev/null) && [ -n "$out" ]; then
        echo "$out"; return 0
    fi
    backend=$(docker ps -q \
        --filter "label=com.docker.compose.project.working_dir=$PROJECT_DIR" \
        --filter "label=com.docker.compose.service=backend-component" | head -n 1)
    if [ -n "$backend" ] && out=$(printf '%s' "$pw" | docker exec -i "$backend" python3 -c "$code" 2>/dev/null) && [ -n "$out" ]; then
        echo "$out"; return 0
    fi
    return 1
}

echo "=== OPCP Login Issue Troubleshooting ==="
echo ""
echo "🔌 PostgreSQL: $DB_HOST:$DB_PORT / $DB_NAME (user: $DB_USER)"
echo ""

echo "1. Checking Docker containers..."
docker-compose ps

echo ""
echo "2. Checking backend health..."
curl -s http://ai-OPCP:6000/health | jq . || echo "❌ Backend not responding"

echo ""
echo "3. Checking $ADMIN_EMAIL in the users table..."
if ! run_psql -c "SELECT id, email, role, is_email_verified FROM users WHERE email = '$ADMIN_EMAIL';" </dev/null; then
    echo "❌ Could not query the postgres database"
    exit 1
fi

echo ""
echo "4. Set/modify the password for $ADMIN_EMAIL"
ADMIN_PASSWORD=""
read -r -p "Change the password now? (y/n): " CHANGE_PW
if [[ "$CHANGE_PW" =~ ^[Yy]$ ]]; then
    while true; do
        read -r -s -p "New password for $ADMIN_EMAIL: " PW1; echo ""
        read -r -s -p "Confirm password: " PW2; echo ""
        if [ -z "$PW1" ]; then
            echo "❌ Password cannot be empty"
        elif [ "$PW1" != "$PW2" ]; then
            echo "❌ Passwords do not match"
        elif [ "$(printf '%s' "$PW1" | wc -c)" -gt 72 ]; then
            echo "❌ Password cannot be longer than 72 bytes (bcrypt limit)"
        else
            break
        fi
    done

    if PW_HASH=$(hash_password "$PW1"); then
        RESULT=$(printf '%s\n' "UPDATE users SET password_hash = :'pwhash', updated_at = NOW() WHERE email = :'email' RETURNING id;" \
            | run_psql -t -A -v "pwhash=$PW_HASH" -v "email=$ADMIN_EMAIL") || { echo "❌ Password update failed"; exit 1; }
    else
        # No bcrypt available on the host or in the backend container: hash inside postgres
        # with pgcrypto (bcrypt $2a$, accepted by the app's bcrypt.checkpw). The password is
        # sent hex-encoded on stdin so it never appears in a process list or needs SQL escaping.
        echo "ℹ️  python bcrypt not available, hashing with postgres pgcrypto"
        PW_HEX=$(printf '%s' "$PW1" | od -An -v -tx1 | tr -d ' \n')
        RESULT=$(printf '%s\n' \
            "CREATE EXTENSION IF NOT EXISTS pgcrypto;" \
            "UPDATE users SET password_hash = crypt(convert_from(decode('$PW_HEX', 'hex'), 'UTF8'), gen_salt('bf', 12)), updated_at = NOW() WHERE email = '$ADMIN_EMAIL' RETURNING id;" \
            | run_psql -t -A -q) || { echo "❌ Password update failed (pgcrypto unavailable?)"; exit 1; }
    fi
    if echo "$RESULT" | grep -q .; then
        echo "✅ Password updated for $ADMIN_EMAIL"
        ADMIN_PASSWORD="$PW1"
    else
        echo "❌ User $ADMIN_EMAIL not found in users table; nothing updated."
        echo "   Create it with: docker-compose exec ai-OPCP python3 scripts/verify_admin_user.py"
    fi
    unset PW1 PW2 PW_HASH PW_HEX
fi

echo ""
echo "5. Testing API endpoint directly..."
if [ -n "$ADMIN_PASSWORD" ]; then
    echo "Attempting login with $ADMIN_EMAIL..."
    jq -n --arg e "$ADMIN_EMAIL" --arg p "$ADMIN_PASSWORD" '{email:$e,password:$p}' \
      | curl -X POST http://ai-OPCP:6000/api/auth/login \
          -H "Content-Type: application/json" -d @- -v
else
    echo "Skipped (no new password entered)."
fi
unset ADMIN_PASSWORD

echo ""
echo ""
echo "6. Checking nginx logs for errors..."
docker-compose logs --tail=50 nginx | grep -i error || echo "No errors in nginx logs"

echo ""
echo "7. Checking backend logs for errors..."
docker-compose logs --tail=50 ai-OPCP | grep -i error || echo "No errors in backend logs"

echo ""
echo "=== Troubleshooting Complete ==="
echo ""
echo "Common issues and solutions:"
echo "1. Email not verified: Run 'docker-compose exec ai-OPCP python3 scripts/verify_admin_user.py'"
echo "2. Wrong password: re-run this script and set a new password"
echo "3. API not accessible: Check if backend is running on port 6000"
echo "4. CORS issues: Check browser console for CORS errors"
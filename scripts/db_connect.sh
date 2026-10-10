#!/bin/bash
# Helper script to connect to the PostgreSQL database
# This prevents "role root does not exist" errors

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
else
    echo "❌ Error: .env file not found"
    exit 1
fi

# Parse DATABASE_URL to extract connection details
# Format: postgresql://user:password@host:port/database
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL not set in .env"
    exit 1
fi

# Extract connection details using regex
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo "🔌 Connecting to PostgreSQL database..."
echo "   Host: $DB_HOST:$DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo ""

# Connect using docker-compose exec to avoid host connection issues
docker-compose exec -e PGPASSWORD="$DB_PASS" postgres psql -U "$DB_USER" -d "$DB_NAME"

# Database Access Guide

## Common Error: "role root does not exist"

This error occurs when trying to connect to PostgreSQL without specifying the correct user credentials. PostgreSQL defaults to using your system username (often "root" or your current user) if no user is specified.

## Solution

Always use one of these methods to access the database:

### Method 1: Use the Helper Script (Recommended)

```bash
./scripts/db_connect.sh
```

This script automatically reads your `.env` file and connects with the correct credentials.

### Method 2: Connect via Docker Compose

```bash
# Interactive psql session
docker-compose exec postgres psql -U OPCP_user -d OPCP_db

# Run a single SQL command
docker-compose exec postgres psql -U OPCP_user -d OPCP_db -c "SELECT * FROM users LIMIT 5;"

# Run SQL from a file
docker-compose exec -T postgres psql -U OPCP_user -d OPCP_db < backup.sql
```

### Method 3: Direct Connection (if PostgreSQL client is installed)

```bash
# Set password to avoid prompt
export PGPASSWORD='OPCP_password'

# Connect
psql -h localhost -p 6002 -U OPCP_user -d OPCP_db
```

## Database Credentials

The database credentials are defined in your `.env` file:

```env
DATABASE_URL=postgresql://OPCP_user:OPCP_password@postgres:5432/OPCP_db
```

- **User**: `OPCP_user`
- **Password**: `OPCP_password` (change in production!)
- **Host**: `postgres` (inside Docker network) or `localhost` (from host)
- **Port**: `5432` (inside Docker) or `6002` (exposed to host)
- **Database**: `OPCP_db`

## Common Database Operations

### Backup Database

```bash
# Using the backup script (recommended)
python3 scripts/backup_database_universal.py

# Manual backup
docker-compose exec postgres pg_dump -U OPCP_user -d OPCP_db -F c -f /tmp/backup.sql
docker cp $(docker-compose ps -q postgres):/tmp/backup.sql ./backups/
```

### Restore Database

```bash
# Using the restore script
python3 scripts/restore_database.py ./backups/backup.sql

# Manual restore
docker cp ./backups/backup.sql $(docker-compose ps -q postgres):/tmp/restore.sql
docker-compose exec postgres pg_restore -U OPCP_user -d OPCP_db -c /tmp/restore.sql
```

### View Database Logs

```bash
docker-compose logs -f postgres
```

### Check Database Status

```bash
docker-compose exec postgres pg_isready -U OPCP_user -d OPCP_db
```

## Troubleshooting

### Container Name Issues

If you see errors about container names, check your docker-compose configuration:

```bash
# List running containers
docker-compose ps

# The postgres service should be named 'postgres' in docker-compose.yml
# The DATABASE_URL in .env should match: @postgres:5432
```

### Connection Refused

If you can't connect from the host machine:

1. Check that the port is exposed in `docker-compose.yml`:
   ```yaml
   ports:
     - "${HTTPS_PORT2:-6002}:5432"
   ```

2. Use the exposed port when connecting from host:
   ```bash
   psql -h localhost -p 6002 -U OPCP_user -d OPCP_db
   ```

### Permission Denied

If you get permission errors:

1. Check that the user has proper privileges:
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE OPCP_db TO OPCP_user;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO OPCP_user;
   ```

2. Ensure the password is correct in `.env`

## Security Notes

- Never commit `.env` file with real credentials
- Change default passwords in production
- Use strong passwords (minimum 16 characters)
- Restrict database port exposure in production
- Enable SSL/TLS for database connections in production

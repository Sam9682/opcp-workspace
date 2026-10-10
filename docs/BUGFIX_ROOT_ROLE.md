# Bugfix: "role root does not exist" Error

## Problem

PostgreSQL container logs showed:
```
FATAL: role "root" does not exist
```

This error occurs when attempting to connect to PostgreSQL without specifying the correct user credentials.

## Root Cause

1. The `.env` file had incorrect hostname (`@db:5432` instead of `@postgres:5432`)
2. Missing `POSTGRES_PASSWORD` environment variable
3. Users attempting to connect directly without proper credentials

## Solution Applied

### 1. Fixed `.env` Configuration

**Before:**
```env
DATABASE_URL=postgresql://OPCP_user:OPCP_password@db:5432/OPCP_db
```

**After:**
```env
DATABASE_URL=postgresql://OPCP_user:OPCP_password@postgres:5432/OPCP_db
POSTGRES_PASSWORD=OPCP_password
```

The hostname must match the service name in `docker-compose.yml` (which is `postgres`).

### 2. Created Helper Script

Created `scripts/db_connect.sh` to provide easy database access:

```bash
./scripts/db_connect.sh
```

This script:
- Reads credentials from `.env`
- Connects via docker-compose to avoid host connection issues
- Prevents "role root does not exist" errors

### 3. Added Documentation

Created `docs/DATABASE_ACCESS.md` with:
- Explanation of the error
- Multiple connection methods
- Common database operations
- Troubleshooting guide

## How to Verify the Fix

1. **Restart containers:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

2. **Check container logs:**
   ```bash
   docker-compose logs postgres
   ```
   Should show no "role root" errors.

3. **Test database connection:**
   ```bash
   ./scripts/db_connect.sh
   ```
   Should connect successfully.

4. **Test application:**
   ```bash
   curl http://localhost:6000/health
   ```
   Should return healthy status.

## Prevention

To prevent this error in the future:

1. **Always use the helper script** for database access
2. **Never run `psql` or `pg_dump` without specifying `-U OPCP_user`**
3. **Use docker-compose exec** for database operations
4. **Keep `.env` and `docker-compose.yml` service names in sync**

## Related Files Modified

- `.env` - Fixed DATABASE_URL hostname and added POSTGRES_PASSWORD
- `.env.example` - Updated template with correct configuration
- `scripts/db_connect.sh` - New helper script for database access
- `docs/DATABASE_ACCESS.md` - New documentation for database operations
- `docs/BUGFIX_ROOT_ROLE.md` - This file

## Additional Notes

The error appeared in logs but didn't necessarily break the application. It typically occurs when:
- Running manual database commands from the host
- Scripts that don't properly set credentials
- Health checks or monitoring tools using default credentials

The application itself uses `DATABASE_URL` from `.env` and connects correctly.

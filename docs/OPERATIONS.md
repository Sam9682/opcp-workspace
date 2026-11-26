# Operations: backups, restore and database access

## Database access

`scripts/db_connect.sh` finds the PostgreSQL container of the current deployment and opens `psql` with the credentials from the environment or `.env`:

```bash
./scripts/db_connect.sh                                    # interactive psql (run from the repo root)
echo "SELECT count(*) FROM users;" | ./scripts/db_connect.sh
```

Manual alternative:

```bash
docker exec -it opcp-workspace-postgres-<USER_ID>-5432 psql -U shai_user -d shai_db
```

Always pass `-U`. Without it, `psql` connects as the OS user (`root`) and fails with `role "root" does not exist`.

From the host, PostgreSQL is published on `HTTPS_PORT2` (see [DEPLOYMENT.md](DEPLOYMENT.md#ports)).

## Backups

### Local dump (`scripts/backup.sh`)

`deployApp.sh start` regenerates `scripts/backup.sh` with the deployment's project name and ports. The script runs `pg_dump` inside the PostgreSQL container, writes `backups/opcp-workspace_backup_<date>.sql.gz` and keeps the last 7 backups.

The generated script uses the user and database from `.env.prod` (`POSTGRES_USER`/`POSTGRES_DB`) and defaults to `opcp-workspace`. The Compose database is `shai_db`/`shai_user`, so check the credentials before relying on it.

### S3 backups (AWS or OVH Object Storage)

`scripts/backup_database_universal.py` runs `pg_dump -F c` (using `DATABASE_URL`) into `./backups/OPCP_backup_<timestamp>.sql`. It then uploads the dump to `s3://<bucket>/<YYYY>/<MM>/<DD>/` with server-side encryption.

```bash
# OVH Object Storage
export OVH_S3_ACCESS_KEY=... OVH_S3_SECRET_KEY=...
export OVH_S3_ENDPOINT=https://s3.gra.io.cloud.ovh.net OVH_S3_REGION=gra   # defaults
python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket <bucket>

# AWS (standard credential chain)
python scripts/backup_database_universal.py --s3-provider aws --s3-bucket <bucket>

# Options
#   --backup-dir ./backups    local directory
#   --retention-days 30       local retention
#   --no-s3                   local dump only
#   --list                    list backups
```

`scripts/backup_database.py` is the older AWS-only variant. Check your setup with `python scripts/test_backup_setup.py`.

To run it daily, add a cron entry on the host, for example:

```cron
0 3 * * * cd /path/to/opcp-workspace && venv/bin/python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket <bucket>
```

## Restore

```bash
# From a local dump (custom format)
python scripts/restore_database.py backups/OPCP_backup_<timestamp>.sql

# From S3
python scripts/restore_from_s3_universal.py --provider ovh --bucket <bucket> list [--prefix 2026/11/]
python scripts/restore_from_s3_universal.py --provider ovh --bucket <bucket> download <s3_key> [--local-dir ./backups]
python scripts/restore_from_s3_universal.py --provider ovh --bucket <bucket> restore <s3_key>

# From a gzipped plain dump produced by scripts/backup.sh
gunzip -c backups/opcp-workspace_backup_<date>.sql.gz | \
  docker exec -i opcp-workspace-postgres-<USER_ID>-5432 psql -U shai_user -d shai_db
```

Stop the backend during a restore. After restoring, restart it so pending migrations are applied.

If field encryption was enabled, the restored data can only be read with the same password key (see [SECURITY.md](SECURITY.md#database-field-encryption)).

More detail: `scripts/README_BACKUP.md`.

## Administrator account recovery

```bash
docker exec -it <backend-container> python scripts/verify_admin_user.py
```

This interactive script checks the `admin@opcp-psmc.com` account using the application's database settings. If the account is missing, it recreates it with the default password `Admin1234!`. It also offers to mark the email as verified and tests the password.

## Logs and health

```bash
./deployApp.sh logs <USER_ID>
docker logs -f <backend-container>
curl -k https://<domain>:<HTTPS_PORT>/health
```

The backend also writes `logs/app.log` inside the container. It is not rotated.

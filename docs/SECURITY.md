# Security, authentication and GDPR

## Authentication

- **Passwords**: bcrypt hashes. A password needs at least 8 characters, with at least one uppercase letter, one lowercase letter and one digit.
- **Sessions**: JWT (`HS256`, signed with `SECRET_KEY`), valid `ACCESS_TOKEN_EXPIRE_MINUTES` (30 by default). Logging out adds the token to `token_blacklist`.
- **Email verification**: registration sends a verification link valid for 24 hours. Unverified users cannot log in. Administrators can override verification from the members page.
- **Password reset**: `POST /api/auth/password-reset` sends a link valid for 1 hour. `/reset-password` in the UI completes the reset.
- **Blocked memberships**: users whose `membership_status` is `expired` or `suspended` cannot log in. The attempt is written to the audit log.
- **Default administrator**: `admin@opcp-psmc.com` / `Admin1234!` is created on an empty database. Change the password immediately.

### Two-factor authentication

Users manage 2FA on **Account → Security** (`/account/security`):

- **TOTP**: `POST /2fa/totp/setup` returns a secret and an `otpauth://` URI that the UI renders as a QR code. `/2fa/totp/confirm` activates it once a valid code is entered.
- **Email code**: a 6-digit code is emailed at login. This requires working SMTP.

When 2FA is on, `/api/auth/login` returns a challenge, valid 5 minutes, which `/api/auth/login/2fa` completes.

## Rate limiting

slowapi, keyed on the client IP, with in-memory storage. Limits are therefore per backend process and reset on restart.

| Scope | Limit |
|-------|-------|
| Default | 100/minute |
| Registration | 10/hour |
| Login | 20/hour per IP, and 5 failed attempts per 15 minutes per email |
| Email verification, password reset, 2FA endpoints | 5–10/hour |
| Oracle `/ask`, `/ask/stream` | 10/minute |
| Oracle `/analyze/forum` | 5/hour |
| Admin mutations | 30/hour (announcements: 10/hour) |
| Payment initiation | 10/hour |

## Audit log

Administrative actions are written to `audit_log`: role, membership and verification changes, deactivation, document download and delete, configuration changes, and denied logins. Administrators read them on the admin pages (`/api/admin/audit-log`, `/api/admin/login-logs`).

## GDPR

| Endpoint | Effect |
|----------|--------|
| `GET /api/users/me/export` | Returns all personal data of the caller as JSON (profile, forum topics and posts, payments, event registrations) |
| `DELETE /api/users/me` | Deactivates the account immediately and schedules anonymisation 30 days later. The request is refused (409) if a deletion is already scheduled |

The daily 02:00 job (`UserDeletionService.process_scheduled_deletions`) anonymises the personal data of accounts whose deletion date has passed.

## Database field encryption

Optional, application-level encryption of a few free-text columns:

- `forum_topics.title`, `forum_posts.content`
- `users.first_name`, `users.last_name`
- `notifications.content`, `events.description`, `tasks.description`

It is disabled by default, so these columns are stored in plaintext.

How it works (`app/security/`):

- An administrator sets a password key on **Admin → Configuration** (`PUT /api/admin/encryption-config`). A Fernet key is derived from it with PBKDF2-HMAC-SHA256 and a random salt. Only a separate verification hash is stored; the key itself is never persisted.
- Existing rows are converted offline. The script encrypts or decrypts every row in scope and only then flips `encryption_config.enabled`:

  ```bash
  python scripts/migrate_encryption.py --enable     # or --disable; --batch-size 500
  # password key from DB_ENCRYPTION_PASSWORD or an interactive prompt
  ```

- To decrypt after a restart without re-entering the key, set `DB_ENCRYPTION_KEY` to the derived Fernet key.

> ⚠️ If encryption is enabled and both the password key and `DB_ENCRYPTION_KEY` are lost, the encrypted data is **permanently unrecoverable**.

Back up the database before running the migration script. See `scripts/README.md` for the full procedure.

## OpenStack credentials (prerequisites)

The prerequisites module stores an OpenStack application credential per installation. The secret is write-only: it is never returned by the API and never logged. It is stored as Fernet ciphertext under a key derived from `SECRET_KEY`. Keystone tokens are used server-side only. Rotating `SECRET_KEY` makes stored secrets unreadable, so re-enter them afterwards.

## CORS

`ALLOWED_ORIGINS` (comma-separated) configures FastAPI's `CORSMiddleware`, with credentials allowed. In the Docker deployment the browser talks to a single origin through nginx, so CORS only matters for development or other hosts.

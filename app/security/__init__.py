"""Application-level database field encryption package.

This package provides opt-in, application-level encryption for a small set of
non-indexed free-text database columns. Encryption is controlled by an admin
Configuration toggle and a password key supplied by the administrator.

Modules:
- ``encryption``: key derivation (PBKDF2), verification hashing, and Fernet
  encrypt/decrypt primitives.
- ``key_provider``: a process-level singleton holding the active Fernet key in
  memory (never persisted in recoverable form).
- ``types``: the ``EncryptedString`` SQLAlchemy ``TypeDecorator`` that
  transparently encrypts on write and decrypts on read.
- ``config_service``: read/write helpers for the ``encryption_config`` table
  (enabled flag + salted verification hash).

Design notes:
- The password key is never persisted. Only a salted PBKDF2 verification hash
  is stored, so the app can validate a supplied key but cannot recover it.
- Encryption is non-deterministic (Fernet), so in-scope columns must never be
  used in ``WHERE`` / ``ORDER BY`` / ``UNIQUE`` clauses.
"""

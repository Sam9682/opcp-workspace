"""TOTP (time-based one-time password) helpers built on pyotp.

Thin wrappers over ``pyotp`` so the router and tests share one
implementation. Supports Requirements 5.1 and 5.3 (TOTP secret
generation, provisioning URI for QR rendering, and code verification).
"""

import pyotp

ISSUER = "OPCP"


def generate_secret() -> str:
    """Return a new base32 TOTP secret."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    """otpauth:// URI for QR rendering."""
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER)


def verify_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """Validate a submitted TOTP code (±1 step tolerance for clock drift)."""
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=valid_window)

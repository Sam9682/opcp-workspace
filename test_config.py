#!/usr/bin/env python3
"""Test script to verify configuration loading"""

from app.config import settings

print("Testing configuration loading...")
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print(f"PG_PASSWORD: {settings.PG_PASSWORD}")
print(f"PG_HOST: {settings.PG_HOST}")
print(f"PG_USER: {settings.PG_USER}")
print(f"PG_DB: {settings.PG_DB}")

# Test if we can parse the database URL
from urllib.parse import urlparse
parsed = urlparse(settings.DATABASE_URL)
print(f"Parsed DB URL host: {parsed.hostname}")
print(f"Parsed DB URL user: {parsed.username}")
print(f"Parsed DB URL path: {parsed.path}")
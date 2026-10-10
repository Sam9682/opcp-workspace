#!/usr/bin/env bash
# Run the account-security backend test suite, one file at a time with timeouts.
cd ~/workspace/forgejo/ai-shai-web-interface || exit 1

FILES=(
  tests/test_account_security_login_passthrough.py
  tests/test_totp_setup_response.py
  tests/test_email_2fa_enable.py
  tests/test_change_password_audit.py
  tests/test_change_password_property.py
  tests/test_totp_confirmation_guard_property.py
  tests/test_totp_login_enforcement_property.py
  tests/test_login_2fa_email_property.py
  tests/test_account_security_migration.py
)

for f in "${FILES[@]}"; do
  OUT=$(timeout 150 python3 -m pytest "$f" -p no:cacheprovider -q --no-header -o addopts="" 2>&1)
  CODE=$?
  LINE=$(echo "$OUT" | grep -E '(passed|failed|error|skipped|no tests ran)' | tail -1)
  if [ $CODE -eq 124 ]; then
    echo "HANG(150s): $(basename $f)"
  else
    echo "$(basename $f): $LINE"
  fi
  if echo "$LINE" | grep -qE 'failed|error'; then
    echo "----- detail -----"
    echo "$OUT" | grep -E 'FAILED|ERROR|assert|Error' | head -20
  fi
done
echo "DONE_BACKEND_AS"

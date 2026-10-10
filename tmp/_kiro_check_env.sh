#!/usr/bin/env bash
cd ~/workspace/forgejo/ai-shai-web-interface || exit 1
echo "=== python ==="
which python3
python3 --version
echo "=== relevant packages (system) ==="
pip3 list 2>/dev/null | grep -iE 'openai|psycopg2|fastapi|pytest|hypothesis|pydantic|sqlalchemy'
echo "=== find venvs ==="
find . -maxdepth 3 -name 'activate' -path '*/bin/*' 2>/dev/null | head

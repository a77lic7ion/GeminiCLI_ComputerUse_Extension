#!/usr/bin/env bash
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
SERVERS_DIR="$EXT_DIR/servers"
VENV="$SERVERS_DIR/computerusemcp"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[computer_use] EXT_DIR=$EXT_DIR" >&2
echo "[computer_use] SERVERS_DIR=$SERVERS_DIR" >&2
echo "[computer_use] VENV=$VENV" >&2

# 1) Create venv if missing
if [ ! -x "$VENV/bin/python3" ]; then
  echo "[computer_use] creating venv..." >&2
  "$PYTHON_BIN" -m venv "$VENV" 1>&2
  "$VENV/bin/pip" install -U pip wheel setuptools --disable-pip-version-check -q 1>&2
fi

# 2) Install deps from requirements.txt (idempotent)
if [ -f "$SERVERS_DIR/requirements.txt" ]; then
  echo "[computer_use] installing Python dependencies..." >&2
  "$VENV/bin/pip" install -r "$SERVERS_DIR/requirements.txt" \
    --disable-pip-version-check --no-input -q 1>&2
else
  echo "[computer_use] WARNING: $SERVERS_DIR/requirements.txt not found; skipping." >&2
fi

# 3) Ensure Playwright Chromium is installed for THIS venv
echo "[computer_use] ensuring Chromium is installed..." >&2
if ! "$VENV/bin/playwright" install chromium --with-deps --force --no-input -q 1>&2; then
  echo "[computer_use] ERROR: playwright chromium install failed" >&2
  exit 1
fi

# 4) Start MCP server (stdout must remain clean; logs go to stderr)
echo "[computer_use] starting MCP server..." >&2
exec "$VENV/bin/python3" "$SERVERS_DIR/computer_use_mcp.py" "$@"

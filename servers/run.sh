#!/usr/bin/env bash
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
SERVERS_DIR="$EXT_DIR/servers"
# Rename VENV to reflect its new purpose (computerusemcp)
VENV="$SERVERS_DIR/computerusemcp" 
PYTHON_BIN="${PYTHON_BIN:-python3}"

# 1) Create venv if missing
if [ ! -x "$VENV/bin/python3" ]; then
  echo "[computer_use] creating venv at $VENV" >&2
  "$PYTHON_BIN" -m venv "$VENV" 1>&2
  "$VENV/bin/pip" install -U pip wheel setuptools --disable-pip-version-check -q 1>&2
fi

# 2) Ensure deps (idempotent). All output -> STDERR.
if [ -f "$SERVERS_DIR/requirements.txt" ]; then
  echo "[computer_use] installing Python dependencies..." >&2
  "$VENV/bin/pip" install -r "$SERVERS_DIR/requirements.txt" \
    --disable-pip-version-check --no-input -q 1>&2
fi

# 2.5) ADD PLAYWRIGHT BROWSER INSTALLATION HERE
# Use the python binary in the venv to execute the playwright install command.
# This should be idempotent, but we'll check for success before proceeding.
echo "[computer_use] installing Chromium browser for Playwright (if needed)..." >&2
"$VENV/bin/playwright" install chromium --with-deps --force --no-input -q 1>&2

# 3) Exec the MCP server (this must be the ONLY thing that writes to STDOUT)
echo "[computer_use] starting MCP server..." >&2
exec "$VENV/bin/python3" "$SERVERS_DIR/computer_use_mcp.py"
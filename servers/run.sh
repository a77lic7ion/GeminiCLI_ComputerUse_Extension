#!/usr/bin/env bash
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
SERVERS_DIR="$EXT_DIR/servers"

# venv dedicated to this server
VENV="$SERVERS_DIR/computerusemcp"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[computer_use] using EXT_DIR=$EXT_DIR" >&2
echo "[computer_use] using SERVERS_DIR=$SERVERS_DIR" >&2
echo "[computer_use] using VENV=$VENV" >&2

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

# 3) Ensure Playwright browsers (Chromium) are installed into *this* venv
echo "[computer_use] installing Chromium for Playwright (if needed)..." >&2
if ! "$VENV/bin/playwright" install chromium --with-deps --force --no-input -q 1>&2; then
  echo "[computer_use] ERROR: playwright chromium install failed" >&2
  exit 1
fi

# Optional: let you force headful by exporting CU_HEADFUL=1 before running
# Optional: set CU_NO_SANDBOX=1 if your Linux env requires it (only on trusted boxes!)
# These envs are read by your Python server if you added the small patch I showed earlier.

echo "[computer_use] starting MCP server..." >&2
exec "$VENV/bin/python3" "$SERVERS_DIR/computer_use_mcp.py" "$@"

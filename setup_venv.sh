#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -x .venv/bin/python ] && ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  rm -rf .venv
fi

if [ ! -x .venv/bin/python ]; then
  if ! python3 -m venv .venv >/dev/null 2>&1; then
    rm -rf .venv
    python3 -m pip install --user --break-system-packages virtualenv
    python3 -m virtualenv .venv
  fi
fi

if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  rm -rf .venv
  python3 -m pip install --user --break-system-packages virtualenv
  python3 -m virtualenv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
find "$ROOT/.venv" -type d -name "__pycache__" -prune -exec rm -rf {} +

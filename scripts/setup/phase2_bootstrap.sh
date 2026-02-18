#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not installed. Install from https://docs.astral.sh/uv/"
  exit 1
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example"
fi

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

echo "Syncing dependencies with uv..."
uv sync

echo "Running Phase 2 connectivity verification..."
uv run python "$ROOT_DIR/scripts/setup/verify_phase2_connections.py"

echo
echo "Phase 2 bootstrap complete."
echo "Next: run 'uv run uvicorn main:app --reload' and test /health + /api/prototype/query."

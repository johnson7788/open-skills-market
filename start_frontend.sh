#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is not installed."
  exit 1
fi

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
  npm install
fi

export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:8000}"

exec npm run dev -- --host 127.0.0.1 --port 5173

#!/usr/bin/env bash
set -euo pipefail
platform_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../platform" && pwd)"
case "${1:-help}" in
  setup)
    "${PYTHON:-python3}" "$platform_root/../scripts/init-local.py"
    cd "$platform_root/backend"
    "${PYTHON:-python3}" -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    cd "$platform_root/frontend/admin"
    npm ci
    ;;
  backend)
    cd "$platform_root/backend"
    exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    ;;
  frontend)
    cd "$platform_root/frontend/admin"
    exec npm run dev -- --host 127.0.0.1
    ;;
  test)
    cd "$platform_root/backend"
    exec .venv/bin/python -m unittest discover -s tests -v
    ;;
  build)
    cd "$platform_root/frontend/admin"
    exec npm run build
    ;;
  verify)
    "$0" test
    "$0" build
    python3 "$platform_root/../scripts/validate-tracker.py"
    ;;
  *)
    printf '%s\n' 'Usage: scripts/platform.sh {setup|backend|frontend|test|build|verify}'
    ;;
esac

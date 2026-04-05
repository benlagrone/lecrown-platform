#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${CRM_ENV_FILE:-${SCRIPT_DIR}/.env}"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

require_env() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing ${ENV_FILE}. Run '${0} init-env' first." >&2
    exit 1
  fi
}

cmd="${1:-help}"

case "${cmd}" in
  init-env)
    if [[ ! -f "${ENV_FILE}" ]]; then
      cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    fi
    echo "CRM env ready at ${ENV_FILE}"
    ;;
  up)
    require_env
    compose up -d
    ;;
  down)
    require_env
    compose down
    ;;
  pull)
    require_env
    compose pull
    ;;
  build)
    require_env
    compose up -d --build --force-recreate
    ;;
  upgrade)
    require_env
    compose pull
    compose up -d
    ;;
  logs)
    require_env
    compose logs -f espocrm espocrm-daemon espocrm-websocket espocrm-db
    ;;
  ps)
    require_env
    compose ps
    ;;
  help|-h|--help)
    cat <<'EOF'
Usage: ops/espocrm/crm.sh <command>

Commands:
  init-env   Copy .env.example to .env if it does not exist
  up         Start the EspoCRM stack
  down       Stop the EspoCRM stack
  pull       Pull the latest container images
  build      Recreate the stack from the current compose config
  upgrade    Pull images and restart the stack
  logs       Tail service logs
  ps         Show service status
EOF
    ;;
  *)
    echo "Unknown command: ${cmd}" >&2
    echo "Run '${0} help' for usage." >&2
    exit 1
    ;;
esac

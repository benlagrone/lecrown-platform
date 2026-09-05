#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

port="${1:-8765}"
host="${CERT_TRACKER_HOST:-127.0.0.1}"

printf 'Opening certification tracker at http://%s:%s/tracker/\n' "$host" "$port"
python3 -m http.server "$port" --bind "$host"

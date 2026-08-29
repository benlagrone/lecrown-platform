#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-https://backoffice.lecrownproperties.com}"
base_url="${base_url%/}"

app_headers="$(mktemp)"
health_body="$(mktemp)"
cleanup() {
  rm -f "$app_headers" "$health_body"
}
trap cleanup EXIT

curl --fail --silent --show-error --location --head \
  --max-time 20 \
  "$base_url/" > "$app_headers"

curl --fail --silent --show-error \
  --max-time 20 \
  "$base_url/api/healthz" > "$health_body"

python3 - "$health_body" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if payload.get("status") != "ok":
    raise SystemExit("Back-office API health did not report status=ok")
print("backoffice app reachable")
print("backoffice same-origin API healthy")
PY

#!/usr/bin/env bash
set -euo pipefail

env_port() {
  local name="$1" default="$2" value=""
  if [ -f .env ]; then
    value="$(grep -E "^${name}=" .env | tail -n 1 | cut -d= -f2- | tr -d '\r')"
  fi
  printf '%s' "${value:-$default}"
}

RETRIEVAL_PORT="$(env_port RETRIEVAL_PORT 8000)"
EVALUATION_PORT="$(env_port EVALUATION_PORT 8001)"
NODE_API_PORT="$(env_port NODE_API_PORT 3001)"

check() {
  local name="$1" url="$2"
  if curl -fsS "$url" >/dev/null; then
    echo "OK   $name  $url"
  else
    echo "FAIL $name  $url" >&2
    return 1
  fi
}

check "retrieval backend" "http://127.0.0.1:${RETRIEVAL_PORT}/api/health"
check "evaluation backend" "http://127.0.0.1:${EVALUATION_PORT}/api/health"
check "node api" "http://127.0.0.1:${NODE_API_PORT}/api/health"

response="$(curl -fsS -X POST "http://127.0.0.1:${NODE_API_PORT}/api/similarity-search" \
  -H "Content-Type: application/json" \
  -d '{"diff":"diff --git a/a.txt b/a.txt\n+hello"}')"

if echo "$response" | grep -q '"matches"'; then
  echo "OK   similarity search returned matches"
else
  echo "FAIL similarity search response:" >&2
  echo "$response" >&2
  exit 1
fi

echo "Smoke test passed."
#!/usr/bin/env bash
# Start CoRaCommit from the prebuilt GHCR images (no local build).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.release.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop / Docker Engine first." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.deploy.example .env
  echo "Created .env from .env.deploy.example. Edit it if needed."
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi

health_url() {
  local service="$1" container_port="$2" mapping host_port
  mapping="$($COMPOSE -f "$COMPOSE_FILE" port "$service" "$container_port" 2>/dev/null | head -n 1)"
  host_port="${mapping##*:}"
  if [ -z "$host_port" ] || [ "$host_port" = "$mapping" ]; then
    host_port="$container_port"
  fi
  echo "http://127.0.0.1:${host_port}/api/health"
}

echo "Pulling prebuilt CoRaCommit images from GHCR..."
if ! $COMPOSE -f "$COMPOSE_FILE" pull; then
  echo "" >&2
  echo "Pull failed. If the packages are private, log in first:" >&2
  echo "  echo \$GHCR_TOKEN | docker login ghcr.io -u <github-user> --password-stdin" >&2
  exit 1
fi

echo "Starting CoRaCommit services..."
$COMPOSE -f "$COMPOSE_FILE" up -d

echo "Waiting for health endpoints..."
urls=(
  "$(health_url retrieval-backend 8000)"
  "$(health_url evaluation-backend 8001)"
  "$(health_url node-api 3001)"
)
for i in $(seq 1 60); do
  ok=0
  for url in "${urls[@]}"; do
    if curl -fsS "$url" >/dev/null 2>&1; then ok=$((ok+1)); fi
  done
  if [ "$ok" -eq 3 ]; then
    echo "All services are healthy."
    echo "Next: install the VSIX, open the CoRaCommit sidebar, set an API key, and generate."
    exit 0
  fi
  sleep 5
done

echo "Services did not become healthy in time. Check logs with:" >&2
echo "  $COMPOSE -f $COMPOSE_FILE logs" >&2
exit 1
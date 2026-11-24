#!/usr/bin/env bash
# One-command install: start the backend stack and install the VS Code extension.
#
#   ./scripts/install.sh            # use prebuilt GHCR images (fallback: source build)
#   ./scripts/install.sh --source   # build the images from source
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="release"
if [ "${1:-}" = "--source" ] || [ "${1:-}" = "source" ]; then
  MODE="source"
fi

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

if [ "$MODE" = "release" ]; then
  echo "Pulling prebuilt CoRaCommit images from GHCR..."
  if ! $COMPOSE -f docker-compose.release.yml pull; then
    echo ""
    echo "Prebuilt images are not available (not published yet or no network)."
    echo "Falling back to a source build."
    MODE="source"
  fi
fi

if [ "$MODE" = "source" ]; then
  COMPOSE_FILE="docker-compose.deploy.yml"
  echo "Building and starting CoRaCommit services from source..."
  $COMPOSE -f "$COMPOSE_FILE" up -d --build
else
  COMPOSE_FILE="docker-compose.release.yml"
  echo "Starting CoRaCommit services from prebuilt images..."
  $COMPOSE -f "$COMPOSE_FILE" up -d
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
    break
  fi
  sleep 5
  if [ "$i" -eq 60 ]; then
    echo "Services did not become healthy in time. Check logs:" >&2
    echo "  $COMPOSE -f $COMPOSE_FILE logs" >&2
    exit 1
  fi
done

VSIX="$ROOT/release/coracommit-2.1.0.vsix"
if [ ! -f "$VSIX" ]; then
  echo "Packaging the VS Code extension..."
  bash "$ROOT/scripts/package_extension.sh"
fi

if command -v code >/dev/null 2>&1; then
  echo "Installing the extension..."
  code --install-extension "$VSIX" --force
  echo ""
  echo "Done. Reload the VS Code window (Developer: Reload Window),"
  echo "open the CoRaCommit sidebar, set an API key, stage a change, and click Generate."
else
  echo ""
  echo "VS Code CLI 'code' was not found. Install the extension manually:"
  echo "  $VSIX"
fi
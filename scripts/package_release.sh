#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/package_extension.sh"

BUNDLE="$ROOT/release/coracommit-2.1.0-bundle.zip"
rm -f "$BUNDLE"
zip -r "$BUNDLE" \
  release/coracommit-2.1.0.vsix \
  docker-compose.deploy.yml \
  docker-compose.release.yml \
  .env.deploy.example \
  README.md DEPLOY.md LICENSE \
  docs \
  scripts \
  resource_demo >/dev/null

sha256sum "$ROOT/release/coracommit-2.1.0.vsix" "$BUNDLE" > "$ROOT/release/checksums.txt"
echo "Release bundle: $BUNDLE"
cat "$ROOT/release/checksums.txt"
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/vscode_extension"

npm ci
npm run compile
npm run package

mkdir -p "$ROOT/release"
VSIX="$(ls -t ./*.vsix | head -1)"
cp "$VSIX" "$ROOT/release/"
echo "Packaged: $ROOT/release/$(basename "$VSIX")"
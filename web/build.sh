#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WEB="$ROOT/web"
mkdir -p "$WEB/dist"
zig build-exe "$ROOT/src/web_core.zig" \
  -target wasm32-freestanding \
  -O ReleaseSmall \
  -fno-entry \
  -rdynamic \
  -femit-bin="$WEB/dist/zanim_web_core.wasm"
echo "$WEB/dist/zanim_web_core.wasm"

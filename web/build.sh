#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mkdir -p "$ROOT/web/dist"
zig build-exe "$ROOT/src/web_core.zig" \
  -target wasm32-freestanding \
  -O ReleaseSmall \
  -fno-entry \
  -rdynamic \
  -femit-bin="$ROOT/web/dist/zanim_web_core.wasm"
echo "$ROOT/web/dist/zanim_web_core.wasm"

#!/bin/sh
# Собрать и запустить tools/lmap_pack.c:  tools/lmap_pack.sh LEVEL.shr OUT.shr  (или LEVEL.shr --check FILE)
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; B="$ROOT/build/lmap_pack"
if [ ! -x "$B" ] || [ "$ROOT/tools/lmap_pack.c" -nt "$B" ] || [ "$ROOT/viewer/lmap.h" -nt "$B" ]; then cc -O2 -Wall -I "$ROOT/viewer" -o "$B" "$ROOT/tools/lmap_pack.c"; fi
exec "$B" "$@"

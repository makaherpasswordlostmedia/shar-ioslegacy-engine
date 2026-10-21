#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=${ME_ONCE_OUT:-build/me/once}
PACK=${SFX_PACK:-$HOME/Downloads/shar-psp/build/audio}
mkdir -p "$OUT"
cc -O2 -w -DAUDIO_HOST -DME_ONCE_OLD=1 -I viewer tests/me/stream_once_host.c viewer/audio.c -lm -o "$OUT/red"
if "$OUT/red" "$PACK/" > "$OUT/red.log"; then echo 'FAIL red did not catch old helper'; exit 1; fi
grep -q 'once=0 normal_loop=1 stop=0' "$OUT/red.log" || { cat "$OUT/red.log"; exit 1; }
cc -O2 -w -DAUDIO_HOST -I viewer tests/me/stream_once_host.c viewer/audio.c -lm -o "$OUT/green"
"$OUT/green" "$PACK/" | tee "$OUT/green.log"
echo 'PASS old helper caught, normal music still loops'

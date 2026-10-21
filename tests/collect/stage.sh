#!/bin/bash
# Only collect and room satellites; asset sources stay read-only.
set -eu
cd "$(dirname "$0")/../.."
REF=${COLLECT_REFERENCE:-$(cd "$(git rev-parse --git-common-dir)/.." && pwd)}
OUT=${1:-build/ship_stage}
for n in 2 3 4 5 6 7; do
 mkdir -p "$OUT/l$n"
 for f in "interiors-l$n.bin" "interiors-l$n-gfx.bin"; do
  src="$REF/build/levels/l$n/$f"
  [ ! -f "build/collect/alllevels/$f" ] || src="build/collect/alllevels/$f"
  cp -c "$src" "$OUT/l$n/$f"
 done
 cp -c "build/collect/alllevels/collect-l$n.shr" "$OUT/l$n/collect-l$n.shr"
done
find "$OUT" -type f \( -name 'collect-l*.shr' -o -name 'interiors-l*.bin' \) -exec shasum -a 256 {} \; >build/collect/alllevels/staged-sha256.txt

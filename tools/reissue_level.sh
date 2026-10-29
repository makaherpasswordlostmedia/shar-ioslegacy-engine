#!/bin/sh
# Перевыпуск уровня тем же конвейером, что дал build/far2_out (TEST26): tools/reissue_level.sh N OUTDIR [TRAFFIC.shr]
# level.shr (far_plain, порядок секций) + mcpr.shr + lmap.shr в OUTDIR/lN/. Правило №488 по умолчанию выключено (SHR_PROP_OWNED_OLD=1), как в TEST26
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
N="$1"; OUT="$2"; TR="${3:-$HOME/Downloads/shar-psp-integ/build/t24d_traffic/l$N/traffic.shr}"
[ -f "$TR" ] || TR="$HOME/Downloads/shar-psp-integ/build/t24d_traffic/traffic.shr"
mkdir -p "$OUT/l$N"
SHR_PROP_OWNED_OLD="${SHR_PROP_OWNED_OLD-1}" SHR_FAR_PLAIN=1 LEVEL="$N" tools/build_level.sh "$OUT/l$N/level.shr" > "$OUT/l$N/build.log" 2>&1
tools/mcp_bake.sh "$OUT/l$N/level.shr" "$TR" "$OUT/l$N/mcpr.shr"
tools/lmap_pack.sh "$OUT/l$N/level.shr" "$OUT/l$N/lmap.shr"

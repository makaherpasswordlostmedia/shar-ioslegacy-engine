#!/bin/bash
# ОСТАТОК 09.10 п. 18 (правка 249): следы шин машин миссии с ИИ в безголовом эмуляторе (tools/smoke.sh SMOKE_HEADLESS=1, сценарий
# tests/skid/ai_scenario.txt: гонка sr2, соперники едут 25 с). Красный -DSKID_AI_OLD=1 (следы только у игрока) — SKID ai=0; зелёный — ai > 0.
#   tests/skid/ai_emu.sh [DIR с данными, по умолчанию build/race_w/stage]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PSPDEV=$ROOT/pspdev PATH=$ROOT/pspdev/bin:$PATH
SRC="${1:-build/race_w/stage}"; OUT=build/gates/skid_ai/$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
for v in new red; do
  F=""; [ $v = red ] && F="-DSKID_AI_OLD=1"
  psp-cmake -S viewer -B "$OUT/build_$v" -DCMAKE_C_FLAGS="$F" > "$OUT/cmake_$v.txt" 2>&1 && cmake --build "$OUT/build_$v" > "$OUT/make_$v.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 1; }
  S="$OUT/stage_$v"; mkdir -p "$S"; (cd "$SRC" && find . -type f) | while read -r f; do mkdir -p "$S/$(dirname "$f")"; cp -c "$SRC/$f" "$S/$f" 2>/dev/null || cp "$SRC/$f" "$S/$f"; done
  cp "$OUT/build_$v/EBOOT.PBP" "$S/EBOOT.PBP"
  SMOKE_HEADLESS=1 SHIP_LEVELS="2 3 4 5 6 7" SMOKE_SCN="$ROOT/tests/skid/ai_scenario.txt" tools/smoke.sh "$S" > "$OUT/smoke_$v.txt" 2>&1
  D=$(grep -o 'build/smoke/[0-9-]*' "$OUT/smoke_$v.txt" | tail -1); rm -rf "$S" "$OUT/build_$v"
  ai=$(grep -a '^SKID' "$D/smoke.txt" 2>/dev/null | tail -1 | sed -n 's/.* ai=\([0-9]*\).*/\1/p'); eval "ai_$v=\${ai:-none}"; echo "$v: $(grep -a '^SKID' "$D/smoke.txt" | tail -1)  ($D)"
done
[ "$ai_red" = 0 ] && [ "$ai_new" != none ] && [ "$ai_new" -gt 0 ] && echo "PASS (красный ai=0, зелёный ai=$ai_new)" || { echo "FAIL (красный ai=$ai_red, зелёный ai=$ai_new)"; exit 1; }

#!/bin/bash
# №419: стеклянная игла L2/L5, тыквы L7, l3_burns L3 — удар машиной разбивает предмет (tests/glass419/host.c).
#   tests/glass419/gate.sh [DIR]   DIR — где level<N>.shr, собранные с правкой (по умолчанию build/b419; нет файла — build/levels/l<N>/level.shr)
# Красные: те же уровни до правки (build/levels/l<N>/level_pre419.shr, экспорт без номеров обломков) и движок -DBREAK_FX_OLD
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/glass419; mkdir -p "$OUT"; DIR="${1:-build/b419}"
V=viewer; . tools/bots/lib.sh
mk() { cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST $1 -I $V -I tools/bots -I tests/glass419 tests/glass419/host.c $BOTS_LIB -lm -o "$2" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }; }
mk "" "$OUT/host"; mk -DBREAK_FX_OLD "$OUT/host_fxold"
NEW=(); OLD=()
for n in 2 3 5 7; do f=$DIR/level$n.shr; [ -f $f ] || f=build/levels/l$n/level.shr; NEW+=($n $f); OLD+=($n build/levels/l$n/level_pre419.shr); done
bad=0
"$OUT/host" build/homer.shr "${OLD[@]}" > "$OUT/red_data.txt" 2>&1 && { echo "КРАСНЫЙ (данные до правки) НЕ ПОЙМАН"; bad=1; } || echo "красный (данные до правки): $(grep -c 'FAIL ' "$OUT/red_data.txt") FAIL, $(grep -m1 'l5\|L5' "$OUT/red_data.txt" | grep FAIL | cut -c1-200)"
"$OUT/host_fxold" build/homer.shr "${NEW[@]}" > "$OUT/red_fx.txt" 2>&1 && { echo "КРАСНЫЙ (BREAK_FX_OLD) НЕ ПОЙМАН"; bad=1; } || echo "красный (BREAK_FX_OLD): $(grep -c 'FAIL ' "$OUT/red_fx.txt") FAIL, $(grep -m1 'FAIL ' "$OUT/red_fx.txt" | cut -c1-200)"
"$OUT/host" build/homer.shr "${NEW[@]}" > "$OUT/green.txt" 2>&1 || bad=1
grep -c "^CHECK.*OK" "$OUT/green.txt" | sed 's/^/зелёный OK: /'; grep "FAIL\|RESULT" "$OUT/green.txt" | head
[ $bad = 0 ] && echo "glass419 gate: PASS" || echo "glass419 gate: FAIL"; exit $bad

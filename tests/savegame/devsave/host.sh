#!/bin/bash
# Правка Роба 335: гейт сохранения разработчика на Маке (tests/savegame/devsave/host.c). Сначала КРАСНЫЙ (обязан упасть):
# сборка с -DGAME_MSN_DEV=0 — загрузка DEV как прежде (новая игра уровня, m0/m1). Потом ЗЕЛЁНЫЙ: запись DEV и состояние миссий
# после загрузки DEV на каждом уровне, чей пакет миссий есть (build/missions/level01.msn, build/levels/l<N>/missions/level0<N>.msn).
#   tests/savegame/devsave/host.sh   -> первая строка итог; build/savegame/devsave_*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
OUT=build/savegame; mkdir -p "$OUT"
for f in build/level.shr build/homer.shr build/missions/level01.msn; do [ -f "$f" ] || { echo "FAIL: нет $f"; exit 1; }; done
PACKS="build/missions/level01.msn"; for n in 2 3 4 5 6 7; do p=build/levels/l$n/missions/level0$n.msn; [ -f "$p" ] && PACKS="$PACKS $p"; done
V=viewer
. tools/bots/lib.sh; LIB="$BOTS_LIB $V/savegame.c"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
$CC tests/savegame/devsave/host.c $LIB -lm -o "$OUT/devsave_host" 2> "$OUT/devsave_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/devsave_build.txt"; exit 1; }
$CC -DGAME_MSN_DEV=0 tests/savegame/devsave/host.c $LIB -lm -o "$OUT/devsave_host_old" 2>> "$OUT/devsave_build.txt" || { echo "FAIL: сборка красного"; exit 1; }
ARGS="build/level.shr build/homer.shr $PACKS"
"$OUT/devsave_host_old" $ARGS > "$OUT/devsave_red.txt" 2>&1; rr=$?
nred=$(grep -c "^CHECK dev\.L.*FAIL" "$OUT/devsave_red.txt")
red=0; if [ $rr -ne 0 ] && [ "$nred" -gt 0 ]; then red=1; echo "красный (DEV как прежде): упал, как должен — провалов $nred, $(grep -m1 'dev\.L1\.current' "$OUT/devsave_red.txt" | cut -c1-110)"
else echo "КРАСНЫЙ НЕ ПОЙМАН: сборка без DEV прошла"; fi
"$OUT/devsave_host" $ARGS > "$OUT/devsave_green.txt" 2>&1; rc=$?
grep "^CHECK\|^RESULT" "$OUT/devsave_green.txt"
levels=$(echo $PACKS | wc -w | tr -d ' ')
if [ $red -eq 1 ] && [ $rc -eq 0 ]; then echo "PASS: красный пойман, зелёный $(grep -m1 RESULT "$OUT/devsave_green.txt") на $levels уровнях"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rc"; exit 1

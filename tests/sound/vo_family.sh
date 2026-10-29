#!/bin/bash
# №180/№184/№467 гейт со счётчиком реплик (безголовый эмулятор, flag saystat → SAYSTAT):
#  1. горящая машина (урон 0,9, 95 с): W_Burn повторяется каждые 22–29 с — новая сборка ≥ 3 реплик, flag burnrepold 1 — ровно 1 (красный контроль флагом)
#  2. герой пешком: длинный прыжок (событие 29) имеет дорожки (pool > 0) и хоть раз говорит; красный контроль — EBOOT базы (EBOOT той же сборки с -DLONGJUMP_AIR_OLD=1 -DBURN_REPEAT_OLD=1): pool 0
# Использование: tests/sound/vo_family.sh DIR_ДАННЫХ_С_НОВЫМ_EBOOT [OLD_EBOOT]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; D=${1:?каталог набора с EBOOT новой сборки}; OLD=${2:-}
run() { SMOKE_HEADLESS=1 SMOKE_SCN=$ROOT/tests/sound/$1.txt SMOKE_MAXT=300 tools/smoke.sh "$2" >/dev/null 2>&1; O=$(ls -dt build/smoke/*/ | head -1); grep -o "SAYSTAT.*" "$O/smoke.txt" | tr ' ' '\n' | grep "^$3:" | head -1; }
okn() { echo "$1" | sed -n 's/.*,ok\([0-9]*\),.*/\1/p'; }; pooln() { echo "$1" | sed -n 's/^[0-9]*:pool\([0-9]*\),.*/\1/p'; }
fail=0
b_new=$(okn "$(run burn_repeat_new "$D" 3)"); b_old=$(okn "$(run burn_repeat_old "$D" 3)")
[ "${b_new:-0}" -ge 3 ] && [ "${b_old:-9}" -eq 1 ] && echo "PASS burn: новая $b_new реплик за 95 с, прежняя (burnrepold) $b_old" || { echo "FAIL burn: новая=$b_new прежняя=$b_old"; fail=1; }
l=$(run homer_vo_467 "$D" 29); pl=$(pooln "$l"); ol=$(okn "$l")
[ "${pl:-0}" -gt 0 ] && [ "${ol:-0}" -ge 1 ] && echo "PASS longjump: дорожек $pl, сказано $ol ($l)" || { echo "FAIL longjump: $l"; fail=1; }
if [ -n "$OLD" ]; then
  R=$(mktemp -d); cp -cR "$D"/. "$R"/ 2>/dev/null || cp -R "$D"/. "$R"/; cp "$OLD" "$R/EBOOT.PBP"
  lo=$(run homer_vo_467 "$R" 29); rm -rf "$R"; po=$(pooln "$lo")
  [ "${po:-1}" -eq 0 ] && echo "PASS красный контроль: база без дорожек longjump ($lo)" || { echo "FAIL красный контроль: у базы дорожки есть ($lo)"; fail=1; }
fi
exit $fail

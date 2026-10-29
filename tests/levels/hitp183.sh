#!/bin/bash
# Гейт №183/№685: при наезде на прохожего реплика героя w_hitp звучит следом за криком прохожего. tests/levels/hitp183.sh EBOOT_НОВЫЙ EBOOT_СТАРЫЙ(-DSND_HITP_QUEUE_OLD=1) ДАННЫЕ
#   красный: старый — SAYSTAT событие 7 ok0 при ударах; зелёный: новый — ok>=1 на семенах 1–3
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; NEW=${1:?}; OLD=${2:?}; D=${3:?}
ok() { o=$(SMOKE_MAXT=1500 tests/seat/run.sh "$2" "$D" "$1" | tail -1); grep -a SAYSTAT "$o/smoke.txt" | tail -1 | grep -o ' 7:[^ ]*' | sed -n 's/.*ok\([0-9]*\),.*/\1/p'; }
r=$(ok "$OLD" tests/smoke_scenes/hitp183.txt); g=1
for s in 1 2 3; do sed "s/^flag repair\$/flag sndseed $s\nflag repair/" tests/smoke_scenes/hitp183.txt > "$ROOT/build/hitp183_$s.txt"; n=$(ok "$NEW" "$ROOT/build/hitp183_$s.txt"); echo "seed $s new ok=$n"; [ "${n:-0}" -ge 1 ] || g=0; done
echo "красный (старый) ok=$r"; [ "${r:-0}" = 0 ] && [ $g = 1 ] && { echo "HITP183: PASS"; exit 0; }; echo "HITP183: FAIL"; exit 1

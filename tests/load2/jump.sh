#!/bin/bash
# Гейт «порядок стриминга после большого прыжка глаза» (L6, пять прыжков foot, tests/load2/jump.txt): новое — видимых недогруженных 0
# не позже 500 мс (JUMPDONE ms) и не больше 5 кадров; красный контроль — сборка с -DJUMPRUSH_OLD=1 обязана быть хуже (хотя бы один прыжок > 300 мс или > 8 кадров).
#   tests/load2/jump.sh NEW_EBOOT_DIR OLD_EBOOT_DIR      (папки с EBOOT.PBP; данные smoke.sh берёт из build/)
cd "$(dirname "$0")/../.."
export SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_MAXT=300 SMOKE_SCN=tests/load2/jump.txt
run() { tools/smoke.sh "$1" > build/jump_gate.log 2>&1; d=$(grep -o "build/smoke/[0-9-]*" build/jump_gate.log | tail -1); grep -E "^JUMPDONE" "$d/smoke.txt"; }
new=$(run "$1"); old=$(run "$2"); bad=0
n=$(echo "$new" | grep -c JUMPDONE); [ "$n" -ge 4 ] || { echo "FAIL: прыжков в новом $n < 4"; bad=1; }
echo "$new" | awk '{split($3,a,"=");split($4,b,"=");if(a[2]>500||b[2]>5)f=1}END{exit f}' || { echo "FAIL: новое хуже 500 мс / 5 кадров"; bad=1; }
echo "$old" | awk '{split($3,a,"=");split($4,b,"=");if(a[2]>300||b[2]>8)f=1}END{exit !f}' || { echo "FAIL: красный (JUMPRUSH_OLD) не оказался хуже"; bad=1; }
echo "новое:"; echo "$new"; echo "прежнее:"; echo "$old"
[ $bad = 0 ] && echo "PASS tests/load2/jump.sh" || echo "FAIL tests/load2/jump.sh"; exit $bad

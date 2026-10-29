#!/bin/bash
# Гейт правки Роба 909 (viewer/far909.h: «высокий взгляд» и полная даль 250 м — по высоте над землёй с гистерезисом, а не по ячейке ленты). Мак, только файлы.
#   tests/horizon/far909.sh [трассы…]   код 0 = OK. Трассы по умолчанию tests/horizon/trace_l*.txt (строки «кадр ey высота_над_землёй ey_ячейки», из HZT смоука: flag hztrace 1).
#   красные: -DFAR909_OLD=1 (прежнее правило: глаз выше ячейки ленты на 8 м), -DFAR909_HOLD=0 -DFAR909_OFF=12.f (без гистерезиса: дрожь у порога даёт несколько эпизодов)
#   зелёный: на проездах нет переключений дали 150<->250, а прыжок с дрожью у порога даёт один эпизод
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
T="${TMPDIR:-/tmp}/f909.$$"; mkdir -p "$T"; F="${@:-$(ls tests/horizon/trace_l*.txt)}"
b() { local n=$1; shift; cc -O1 "$@" tests/horizon/far909_host.c -o "$T/$n" || { echo "FAIL: сборка $n"; exit 1; }; "$T/$n" $F > "$T/$n.txt"; echo $? > "$T/$n.rc"; }
b old -DFAR909_OLD=1; b nohys -DFAR909_HOLD=0 -DFAR909_OFF=12.f; b new
for n in old nohys; do if [ "$(cat $T/$n.rc)" = 0 ]; then echo "FAIL: подброска $n прошла — проверка слепая"; cat "$T/$n.txt"; exit 1; fi; echo "красный как надо ($n): $(grep ^TOTAL $T/$n.txt)"; done
if [ "$(cat $T/new.rc)" != 0 ]; then echo "FAIL: на новом коде есть переключения дали"; cat "$T/new.txt"; exit 1; fi
echo "зелёный: $(grep ^TOTAL $T/new.txt)"; grep ^TRACE "$T/new.txt"; echo PASS

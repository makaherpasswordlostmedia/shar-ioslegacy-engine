#!/bin/bash
# Гейт правки Роба 911 (viewer/horizon_chord.h: лента горизонта идёт по дуге, а не хордой через глаз). Мак, только файлы.
#   tests/horizon/chord911.sh [папка с l1.shr … l7.shr, по умолчанию build/hz150]   код 0 = OK. Сначала КРАСНЫЕ подброски (обязаны упасть), потом ЗЕЛЁНЫЙ.
#   красные: -DHZ_CHORD911_OLD=1 (прежний код: вершины контура без добавок), -DHZ_GAP_DEG=40.f (разрыв допускается слишком большой)
#   зелёный: по всем ячейкам всех 7 уровней лента не ближе 150 м к глазу (радиус 154 м), столбцов не больше буфера
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
D="${1:-$ROOT/build/hz150}"; T="${TMPDIR:-/tmp}/c911.$$"; mkdir -p "$T"; F=""
for L in 1 2 3 4 5 6 7; do [ -f "$D/l$L.shr" ] || { echo "FAIL: нет $D/l$L.shr"; exit 1; }; F="$F $D/l$L.shr"; done
b() { local n=$1; shift; cc -O1 "$@" tests/horizon/chord911_host.c -lm -o "$T/$n" || { echo "FAIL: сборка $n"; exit 1; }; "$T/$n" $F > "$T/$n.txt"; echo $? > "$T/$n.rc"; }
b old -DHZ_CHORD911_OLD=1; b g40 -DHZ_GAP_DEG=40.f; b new
for n in old g40; do if [ "$(cat $T/$n.rc)" = 0 ]; then echo "FAIL: подброска $n прошла — проверка слепая"; cat "$T/$n.txt"; exit 1; fi; echo "красный как надо ($n): $(grep ^TOTAL $T/$n.txt)"; done
if [ "$(cat $T/new.rc)" != 0 ]; then echo "FAIL: на новом коде есть ячейки с хордой ближе 150 м"; cat "$T/new.txt"; exit 1; fi
echo "зелёный: $(grep ^TOTAL $T/new.txt)"; grep ^CHORD "$T/new.txt" | sed 's#.*/##'; echo PASS

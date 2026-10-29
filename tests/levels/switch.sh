#!/bin/bash
# Гейт «переход между уровнями» в эмуляторе (задача 29.09: уровни 2–7 как в оригинале). Сначала КРАСНЫЕ на подложенном плохом
# входе, потом ЗЕЛЁНЫЙ; сверка — tests/levels/switch_check.py (строки LEVEL движка), сценарий — tests/levels/switch_scenario.txt.
#   tests/levels/switch.sh [DIR]    DIR — EBOOT + данные (по умолчанию build/ship_stage: tools/ship.sh --no-install)
#   красный 1 «чужой набор»: в l2/ подложен level.shr уровня 1 — старт «уровня 2» не из его данных, сверка обязана упасть
#   красный 2 «утечка»: flag lvleak (выгрузка уровня забывает PVS и коллизию) — куча после круга 1 -> 2 -> 1 не та же, обязана упасть
#   зелёный: настоящие наборы — круг 1 -> 2 -> 1 (конец уровня 1 событием миссий, газета, MISSION SELECT уровня 2) и обход 3..7
# Первая строка вывода — итог, код 0 = OK; журнал build/gates/switch/<время>/
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
[ -f "$SRC/EBOOT.PBP" ] && [ -f "$SRC/l2/level.shr" ] && [ -f "$SRC/level.shr" ] || {
  echo "FAIL: в $SRC нет EBOOT.PBP / level.shr / l2/level.shr (tools/ship.sh --no-install)"; exit 1; }
T="$ROOT/build/gates/switch/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T"
PY="$ROOT/.venv/bin/python"
SHORT="$T/short.txt"; sed '/^# конец круга 1-2-1/q' tests/levels/switch_scenario.txt > "$SHORT"; echo end >> "$SHORT"
LEAK="$T/leak.txt"; awk '{print} /^flag menu$/{print "flag lvleak"}' "$SHORT" > "$LEAK"
run() {   # сценарий, папка данных -> папка прогона smoke.sh
  local log; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$2" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
res=""; ok=1
# красный 1: подложенный набор уровня (копия-клон, в DIR ничего не меняется)
P="$T/planted"; mkdir -p "$P"; cp -c -R "$SRC/." "$P/" && cp -c "$SRC/level.shr" "$P/l2/level.shr"
D=$(run "$SHORT" "$P"); "$PY" tests/levels/switch_check.py "$D" --short > "$T/red_planted.txt" 2>&1
if [ $? = 0 ]; then ok=0; res="$res; КРАСНЫЙ НЕ ПОЙМАН: чужой набор"; else res="$res; красный (чужой набор): $(grep -m1 'ПРОВАЛ' "$T/red_planted.txt" | sed 's/^ *ПРОВАЛ: //' | cut -c1-120)"; fi
# красный 2: утечка при выгрузке
D=$(run "$LEAK" "$SRC"); "$PY" tests/levels/switch_check.py "$D" --short > "$T/red_leak.txt" 2>&1
if [ $? = 0 ]; then ok=0; res="$res; КРАСНЫЙ НЕ ПОЙМАН: утечка"; else res="$res; красный (утечка): $(grep -m1 'ПРОВАЛ' "$T/red_leak.txt" | sed 's/^ *ПРОВАЛ: //' | cut -c1-120)"; fi
# зелёный
D=$(run tests/levels/switch_scenario.txt "$SRC"); "$PY" tests/levels/switch_check.py "$D" > "$T/green.txt" 2>&1
if [ $? = 0 ]; then res="$res; зелёный: $(tail -1 "$T/green.txt")"; else ok=0; res="$res; НЕ ЗЕЛЁНЫЙ: $(grep -m1 'ПРОВАЛ' "$T/green.txt" | sed 's/^ *ПРОВАЛ: //' | cut -c1-140)"; fi
echo "$([ $ok = 1 ] && echo PASS || echo FAIL)${res}"
echo "зелёный прогон: ${D#$ROOT/} (smoke.txt, снимки l2_spawn, loading, l2_msnsel, l1_again, l3..l7_spawn); журнал ${T#$ROOT/}"
cat "$T/green.txt"
[ $ok = 1 ]

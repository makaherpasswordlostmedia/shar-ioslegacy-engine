#!/bin/bash
# Гейт «свет уровня» в эмуляторе (29.09, рецепт §12): яркость машины и Гомера согласна с миром уровня, 30 FPS, куча ≥ 20 МБ.
#   tests/light/emu_gate.sh [DIR]     DIR — EBOOT.PBP и данные уровня 1 (по умолчанию build/ship_stage)
# Прогоны tests/light/emu.sh (по одному через очередь эмулятора): дневные уровни той же карты в той же точке (1 — для 4 и 7,
# 3 — для 6), ночные 4, 6, 7 со светом уровня и они же с подложенным днём (--pre: тот же level.shr, машина и Гомер в дневном
# свете уровня 1, tests/light/plant_day.py). Красный: день на уровне 6 вместо нового — машина и Гомер ярче мира, K вне [0.75, 1.33].
# Журнал build/gates/light/emu_gate_<время>.log, последняя строка GATE PASS / GATE FAIL.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-build/ship_stage}"
LOG="build/gates/light/emu_gate_$(date +%Y%m%d-%H%M%S).log"; mkdir -p build/gates/light; : > "$LOG"
PY=.venv/bin/python; FAILS=0   # bash 3.2 (macOS): без ассоциативных массивов — переменные RUN_<уровень>[pre]
run() {   # emu.sh N [--pre] -> каталог прогона в RUN[N или Npre]
  local key="$1${2:+pre}" out; out=$(tests/light/emu.sh "$1" ${2:+--pre} "$SRC" 2>&1); echo "$out" >> "$LOG"
  local d; d=$(echo "$out" | sed -n 's/^прогон: //p' | tail -1); printf -v "RUN_$key" '%s' "$d"
  if echo "$out" | grep -q "^замер уровня .*PASS"; then echo "OK прогон уровня $1${2:+ (до света уровня)}: $d" | tee -a "$LOG"
  else echo "ПРОВАЛ прогона уровня $1${2:+ (до света уровня)}: $(echo "$out" | grep ПРОВАЛ | head -3 | tr '\n' ' ')" | tee -a "$LOG"; FAILS=$((FAILS + 1)); fi
}
for n in 1 3; do run $n; done
for n in 4 6 7; do run $n; run $n pre; done
R() { local v="RUN_$1"; echo "${!v:-нет}"; }
cmp_() { $PY tests/light/emu_check.py --new "$(R "$1")" --pre "$(R "$2")" --ref "$(R "$3")" >> "$LOG" 2>&1; }
if cmp_ 6pre 6pre 3; then echo "RED НЕ ПОЙМАН: уровень 6 в дневном свете" | tee -a "$LOG"; FAILS=$((FAILS + 1))
else echo "RED OK: уровень 6 в дневном свете — яркость не согласна с миром" | tee -a "$LOG"; fi
for p in "4 1" "6 3" "7 1"; do set -- $p
  if cmp_ "$1" "$1pre" "$2"; then echo "GREEN OK: уровень $1 — машина и Гомер темнеют вместе с миром" | tee -a "$LOG"
  else echo "GREEN ПРОВАЛ: уровень $1" | tee -a "$LOG"; FAILS=$((FAILS + 1)); fi
done
grep -E "^уровень [0-9] против дня" "$LOG" | sed 's/^/  /'
[ $FAILS = 0 ] && echo "GATE PASS" | tee -a "$LOG" || echo "GATE FAIL ($FAILS)" | tee -a "$LOG"
echo "журнал: $LOG"
[ $FAILS = 0 ]

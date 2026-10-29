#!/bin/bash
# Приёмка №952 (окно «Оптимизация», TEST61): ОДНА команда  tests/tex952/accept60.sh. Последняя строка: PASS или FAIL.
#   1) tests/tex952/flat952.py на 7 уровнях набора выпуска (зелёный: ≥ 10 стен однотонных уходят в заливку, независимая проверка разброса; красный WALL952_OLD=1 обязан упасть)
#   2) tests/toon/flat929.sh (родной асфальт и стены с рисунком остаются текстурой; красный FLAT929_RED=1 падает)
#   3) безголовый эмулятор (tools/emu_run.sh, сценарий flat912): виды L1 с выпускным и с новым flat912.bin (tests/tex952/emu952.py: картинка изменилась, средний цвет тот же, дыр нет); SKIP_EMU=1 пропускает
#   переменные: SET (набор выпуска), DATA (куда класть новые flat912.bin: L1 в корне, lN/), EB (EBOOT с KEEP_SMOKE; по умолчанию набор)
set -u -o pipefail
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PATH="$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH"
PY="${PY:-$HOME/Downloads/shar-psp/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SET="${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}"
DATA="${DATA:-$HOME/Downloads/shar-psp/build/t60/data_tex952}"
EB="${EB:-$W/viewer/build_t60/EBOOT.PBP}"
fail=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
say "1. гейт flat952 (зелёный)"; "$PY" tests/tex952/flat952.py "$SET" "$DATA" | tail -12 || fail=1
say "1. красный контроль: правило выключено (WALL952_OLD=1) — гейт обязан упасть"
if WALL952_OLD=1 "$PY" tests/tex952/flat952.py "$SET" | tail -2; then echo "красный НЕ упал"; fail=1; else echo "красный упал, как должен"; fi
say "2. гейт flat929 (асфальт и стены с рисунком)"; "$PY" tests/toon/flat929.py "$SET" | tail -4 || fail=1
FLAT929_RED=1 bash tests/toon/flat929.sh "$SET" | tail -2 || fail=1
if [ "${SKIP_EMU:-0}" != 1 ]; then
  OUT="${OUT:-$W/build/accept60_tex952}"; mkdir -p "$OUT"; SCN="$W/tests/toon/flat912_scenario.txt"
  say "3. эмулятор: виды L1 с заливкой — старый flat912.bin (выпуск) и новый (№952)"
  SET="$SET" OUT="$OUT" EMU_OWNER="${EMU_OWNER:-opt}" EMU_MINE=1 tools/emu_run.sh "$SCN" old "$EB" 500 > "$OUT/old.out" 2>&1 &
  SET="$SET" OUT="$OUT" EMU_OWNER="${EMU_OWNER:-opt}" EMU_MINE=2 OVL="$DATA" tools/emu_run.sh "$SCN" new "$EB" 500 > "$OUT/new.out" 2>&1 &
  wait; cat "$OUT/old.out" "$OUT/new.out"
  "$PY" tests/tex952/emu952.py "$OUT/out_old" "$OUT/out_new" || fail=1
  say "3. красный контроль: два прогона со старым списком (ничего не изменилось) — гейт обязан упасть"
  if "$PY" tests/tex952/emu952.py "$OUT/out_old" "$OUT/out_old" | tail -2; then echo "красный НЕ упал"; fail=1; else echo "красный упал, как должен"; fi
fi
[ $fail = 0 ] && { echo "ПРИЁМКА №952: PASS"; echo PASS; exit 0; }; echo "ПРИЁМКА №952: FAIL"; echo FAIL; exit 1

#!/bin/bash
# Гейт правки Роба 239 («вышел из игры в главное меню — музыки нет»): QUIT GAME из паузы во время миссии -> в меню набор шин
# Normal и тема simpsons_theme. КРАСНЫЙ: EBOOT с -DFE_PAUSE_OLD=1 (прежнее: набор «Pause» оставался, тишина) обязан упасть.
# ЗЕЛЁНЫЙ: viewer/build/EBOOT.PBP (или QUIT_EBOOT). Эмулятор безоконный, без звука (tools/twins)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/fe_quit; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DFE_PAUSE_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась ($OUT/red_build.txt)"; exit 2; }
"$PY" tests/fe_music/quit_run.py red "$OUT/red_build/EBOOT.PBP" > "$OUT/red.txt" 2>&1; rr=$?
cat "$OUT/red.txt" | tail -1
if [ $rr -ne 0 ] && grep -q "набор шин 1" "$OUT/red.txt"; then echo "красный (-DFE_PAUSE_OLD=1): упал, как должен"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
"$PY" tests/fe_music/quit_run.py green "${QUIT_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/green.txt" 2>&1; rg=$?
cat "$OUT/green.txt" | tail -1
if [ $red -eq 1 ] && [ $rg -eq 0 ]; then echo "PASS: красный пойман, зелёный — в меню Normal и simpsons_theme"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rg"; exit 1

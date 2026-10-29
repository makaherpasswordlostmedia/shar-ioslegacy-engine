#!/bin/bash
# Гейт №627 (запись PS2 ps2-police-after-busted.yaml): после ареста полицейская стоит до конца таймера и пропадает одним шагом, затем затемнение и перенос машины.
# КРАСНЫЙ: EBOOT с -DBUSTED_PS2_OLD=1 (прежнее) обязан упасть. ЗЕЛЁНЫЙ: viewer/build/EBOOT.PBP
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/busted_ps2; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DBUSTED_PS2_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась"; exit 2; }
"$PY" tests/hnr/busted_ps2.py red "$OUT/red_build/EBOOT.PBP" > "$OUT/red.txt" 2>&1; rr=$?; tail -1 "$OUT/red.txt"
if [ $rr -ne 0 ] && grep -q "полицейская убрана в момент ареста" "$OUT/red.txt"; then echo "красный (-DBUSTED_PS2_OLD=1): упал, как должен"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
"$PY" tests/hnr/busted_ps2.py green "${BUST_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/green.txt" 2>&1; rg=$?; tail -1 "$OUT/green.txt"
if [ $red -eq 1 ] && [ $rg -eq 0 ]; then echo "PASS: красный пойман, зелёный — как у оригинала"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rg"; exit 1

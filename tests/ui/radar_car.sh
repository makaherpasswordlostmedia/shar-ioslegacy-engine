#!/bin/bash
# Гейт правки Роба 236 («карта не запоминает, где была машина»): своя машина на радаре, пока Гомер пешком.
# КРАСНЫЙ: EBOOT с -DRADAR_NO_CAR=1 (прежнее: значка нет) обязан упасть. ЗЕЛЁНЫЙ: viewer/build/EBOOT.PBP (или RADAR_EBOOT)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/radar_car; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DRADAR_NO_CAR=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась ($OUT/red_build.txt)"; exit 2; }
"$PY" tests/ui/radar_car.py red "$OUT/red_build/EBOOT.PBP" > "$OUT/red.txt" 2>&1; rr=$?
tail -1 "$OUT/red.txt"
if [ $rr -ne 0 ] && grep -q "машины на радаре нет" "$OUT/red.txt"; then echo "красный (-DRADAR_NO_CAR=1): упал, как должен"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
"$PY" tests/ui/radar_car.py green "${RADAR_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/green.txt" 2>&1; rg=$?
tail -1 "$OUT/green.txt"
if [ $red -eq 1 ] && [ $rg -eq 0 ]; then echo "PASS: красный пойман, зелёный — машина на радаре пешком, в машине нет"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rg"; exit 1

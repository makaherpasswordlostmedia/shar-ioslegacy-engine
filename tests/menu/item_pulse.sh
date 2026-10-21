#!/bin/bash
# Гейт правки 412: пульс выбранного пункта главного меню по числам SLES_518.97 — безголовый эмулятор, ~1 мин.
#   tests/menu/item_pulse.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/ship_stage); красный — сборка -DMENU_PULSE_OLD=1
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
DIR="${1:-build/ship_stage}"; OUT=build/gates/412; mkdir -p "$OUT"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DMENU_PULSE_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка"; exit 2; }
run() { SMOKE_HEADLESS=1 SMOKE_SCN=tests/menu/item_pulse.txt tools/smoke.sh "$1" > /dev/null 2>&1; ls -td build/smoke/2* | head -1; }
G=$(run "$DIR")
rm -rf "$OUT/red"; cp -cR "$DIR" "$OUT/red" 2>/dev/null || cp -R "$DIR" "$OUT/red"; cp "$OUT/red_build/EBOOT.PBP" "$OUT/red/EBOOT.PBP"
R=$(run "$OUT/red")
.venv/bin/python tests/menu/item_pulse.py "$G"; rg=$?
echo "красный (-DMENU_PULSE_OLD=1):"; .venv/bin/python tests/menu/item_pulse.py "$R" --expect-fail; rr=$?
rm -rf "$OUT/red"
[ $rg -eq 0 ] && [ $rr -eq 0 ] && { echo "ИТОГ: PASS (зелёный $G, красный пойман $R)"; exit 0; }
echo "ИТОГ: FAIL (зелёный rc=$rg, красный пойман=$([ $rr -eq 0 ] && echo да || echo НЕТ))"; exit 1

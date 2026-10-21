#!/bin/bash
# Гейт ускорения отрисовки (05.10, viewer/render_fast.h: О2 стейтпропы вне кадра, О4 повтор клетки в dlCity, О11 листы у камеры).
#   tests/render/gate.sh            — хост (cc, ~5 с, без level.shr): настоящий код render_fast.h / ge_guard.h / stateprops.c на
#                                     синтетике; зелёный обязан пройти, красный (-DRF_TEST_BROKEN) обязан упасть по всем трём
#   tests/render/gate.sh --smoke    — плюс эмулятор: смоук со сценарием tests/render/ab_scenario.txt (прежнее flag rfold 7 и
#                                     новое rfold 0 у каждой позы) через tools/ship.sh --no-install, разбор tests/render/rfast.py
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/render; mkdir -p "$OUT"; V=viewer
SRC="tests/render/host.c $V/stateprops.c $V/col.c $V/props.c $V/coins.c $V/car.c"
cc -std=c11 -O2 -w -I$V $SRC -lm -o "$OUT/host" && cc -std=c11 -O2 -w -DRF_TEST_BROKEN -I$V $SRC -lm -o "$OUT/host_red" || { echo "FAIL: сборка"; exit 1; }
"$OUT/host_red" > "$OUT/red.txt"; r=$?
if [ $r -eq 0 ] || [ "$(grep -c 'О2 FAIL, О11 FAIL, О4 FAIL' "$OUT/red.txt")" != 1 ]; then echo "КРАСНЫЙ НЕ ПОЙМАН:"; cat "$OUT/red.txt"; exit 1; fi
echo "красный (RF_TEST_BROKEN: радиус по кадру 0 / клетка в риске всегда листом / метка без стекла): упал по всем трём"
"$OUT/host" > "$OUT/green.txt"; g=$?; sed 's/^/  /' "$OUT/green.txt"
[ $g -eq 0 ] || { echo "ИТОГ: FAIL (хост)"; exit 1; }
if [ "${1:-}" = --smoke ]; then
  bash tests/render/frozen.sh "${RF_EBOOT:-$ROOT/viewer/build/EBOOT.PBP}" || exit 1
fi
echo "ИТОГ: PASS"

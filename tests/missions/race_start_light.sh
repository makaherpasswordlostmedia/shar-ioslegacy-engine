#!/bin/bash
# №старт-гонки (разбор железа TEST19 п. 2): гонка Лизы, первые секунды после Continue — машины миссии (PH4CARS drive, мс на кадр, Мак) не дороже 0,5; красный -DRACE_START_LIGHT_OLD=1 (≥ 0,8)
# Нужен пакет с данными (RACE_PKG, по умолчанию ~/Downloads/shar-psp-sonnet-16b-w/build/test19_emu) и tools/twins/bin/PPSSPPHeadless. Без звука и окна.   tests/missions/race_start_light.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export TWINS_ROOT="$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"; OUT=build/race_start_light; mkdir -p "$OUT"
peak() { awk '/^SCENE R_card_lisa_L3/{r=1} r && /^PH4CARS/{for(i=1;i<=NF;i++) if($i ~ /^drive=/){split($i,a,"="); if(a[2]>m) m=a[2]}} END{print m+0}' "$1/smoke.txt"; }
for v in red green; do
  fl=""; [ $v = red ] && fl="-DCMAKE_C_FLAGS=-DRACE_START_LIGHT_OLD=1"
  psp-cmake -S viewer -B "$OUT/${v}_build" $fl > "$OUT/${v}_cmake.txt" 2>&1 && cmake --build "$OUT/${v}_build" -j4 > "$OUT/${v}_build.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 2; }
  d=$("$ROOT/.venv/bin/python" tests/missions/race_start_light.py "$OUT/${v}_build/EBOOT.PBP" $v | tail -1); eval "${v}_peak=$(peak "$d")"
  . tests/lib/drawn.sh; echo -n "  [$v] "; drawn_check "$d" || { echo "FAIL: куски drawPieceM не уходят в drawGeo (картинка), прогон $v"; exit 1; }
done
echo "машины миссии за первые секунды гонки Лизы, пик мс/кадр: красный (прежнее) $red_peak, зелёный $green_peak"
awk -v r="$red_peak" -v g="$green_peak" 'BEGIN{exit !(r >= 0.8 && g <= 0.5)}' && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }

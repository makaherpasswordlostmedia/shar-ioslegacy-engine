#!/bin/bash
# №prop-fast (аудит FPS п.1: пропы 5,7–7 мс на PSP): скан подписей пропов/стейтпропов — только ближние (60 м) каждый кадр, дальние раз в 8 кадров. Зелёный: время скана (props+sprops, PBPROF)
# не больше 45 % красного (-DPROP_FAST_OLD=1), пересборок клеток (PBAKE) не меньше 75 % красного (сбитые вблизи замечаются как прежде). Безоконный эмулятор, пакет RACE_PKG.   tests/missions/prop_fast.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export TWINS_ROOT="$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"; OUT=build/prop_fast; mkdir -p "$OUT"
scan() { awk '/^SCENE P_drive/{r=1} r && /^PBPROF/{for(i=1;i<=NF;i++){ if($i ~ /^scan=/){split($i,a,"="); s+=a[2]; n++} } } END{printf "%.4f", (n? s/n : 0)}' "$1/smoke.txt"; }
bake() { awk '/^SCENE P_drive/{r=1} r && /^PBAKE/{n++} END{print n+0}' "$1/smoke.txt"; }
for v in red green; do
  fl=""; [ $v = red ] && fl="-DCMAKE_C_FLAGS=-DPROP_FAST_OLD=1"
  psp-cmake -S viewer -B "$OUT/${v}_build" $fl > "$OUT/${v}_cmake.txt" 2>&1 && cmake --build "$OUT/${v}_build" -j4 > "$OUT/${v}_build.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 2; }
  d=$("$ROOT/.venv/bin/python" tests/missions/prop_fast.py "$OUT/${v}_build/EBOOT.PBP" $v | tail -1); eval "${v}_scan=$(scan $d)"; eval "${v}_bake=$(bake $d)"
  . tests/lib/drawn.sh; echo -n "  [$v] "; drawn_check "$d" || { echo "FAIL: куски drawPieceM не уходят в drawGeo (картинка), прогон $v"; exit 1; }
done
echo "скан подписей, мс/кадр (среднее по props и sprops): красный $red_scan, зелёный $green_scan; пересборок клеток: красный $red_bake, зелёный $green_bake"
awk -v rs="$red_scan" -v gs="$green_scan" -v rb="$red_bake" -v gb="$green_bake" 'BEGIN{exit !(rs > 0 && gs <= 0.45*rs && gb >= 0.75*rb)}' && { echo PASS; exit 0; } || { echo FAIL; exit 1; }

#!/bin/bash
# №smk-buf (разбор железа TEST19: «11 кадров io 57–89 мс» = журнал смоука, по одному sceIoWrite на строку, 15–20 строк на границе сцены и старте миссии): записей на карту за прогон
# в 2,5 раза меньше строк и файл полный (END, SMKIO, те же строки миссии); красный -DSMK_BUF_OLD=1 (запись на каждую строку) обязан не пройти порог. Безоконный эмулятор, пакет RACE_PKG.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export TWINS_ROOT="$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"; OUT=build/smk_buf; mkdir -p "$OUT"
for v in red green; do
  fl=""; [ $v = red ] && fl="-DCMAKE_C_FLAGS=-DSMK_BUF_OLD=1"
  psp-cmake -S viewer -B "$OUT/${v}_build" $fl > "$OUT/${v}_cmake.txt" 2>&1 && cmake --build "$OUT/${v}_build" -j4 > "$OUT/${v}_build.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 2; }
  d=$("$ROOT/.venv/bin/python" tests/missions/smk_buf.py "$OUT/${v}_build/EBOOT.PBP" $v | tail -1); eval "${v}_d=$d"
  . tests/lib/drawn.sh; echo -n "  [$v] "; drawn_check "$d" || { echo "FAIL: куски drawPieceM не уходят в drawGeo (картинка), прогон $v"; exit 1; }
  eval "${v}_io=$(grep -m1 '^SMKIO' $d/smoke.txt | sed 's/.*flushes=\([0-9]*\) lines=\([0-9]*\).*/\1:\2/')"
  eval "${v}_plan=$(grep -c '^MSN plan' $d/smoke.txt)"; eval "${v}_end=$(grep -c '^END' $d/smoke.txt)"
done
echo "записей:строк красный $red_io, зелёный $green_io; строк «MSN plan»: $red_plan / $green_plan; END: $red_end / $green_end"
gf=${green_io%%:*}; gl=${green_io##*:}
[ -n "$gl" ] && [ "$gl" -gt 0 ] && [ "$red_plan" = "$green_plan" ] && [ "$green_end" = 1 ] && [ $((gf * 5)) -le $((gl * 2)) ] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }

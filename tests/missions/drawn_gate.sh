#!/bin/bash
# Общий гейт «куски реально рисуются» для всех моих правил (урок 16.10, комментарий проглотил else drawGeo): L1, езда 40 с. Зелёный (все правила по умолчанию): отдано в drawGeo >= 95 % дошедших до рисования,
# CLIPG hidden за езду = 0 (в обычной езде clip-guard ничего не прячет). Красный контроль -DGATE_DROP_DRAW=1 (куски не рисуются, как при баге) обязан дать долю < 50 % и упасть.   tests/missions/drawn_gate.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; export TWINS_ROOT="$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"; OUT=build/drawn_gate; mkdir -p "$OUT"; . tests/lib/drawn.sh
for v in green red; do
  fl=""; [ $v = red ] && fl="-DCMAKE_C_FLAGS=-DGATE_DROP_DRAW=1"
  psp-cmake -S viewer -B "$OUT/${v}_build" $fl > "$OUT/${v}_cmake.txt" 2>&1 && cmake --build "$OUT/${v}_build" -j4 > "$OUT/${v}_build.txt" 2>&1 || { echo "FAIL: сборка $v"; exit 2; }
  d=$(PF_SCEN="$ROOT/tests/missions/prop_fast.txt" "$ROOT/.venv/bin/python" tests/missions/prop_fast.py "$OUT/${v}_build/EBOOT.PBP" dg_$v | tail -1)
  eval "${v}_dir=$d"
done
echo -n "зелёный: "; drawn_check "$green_dir"; gok=$?
echo -n "красный (куски не рисуются): "; drawn_check "$red_dir"; rok=$?
hid=$(awk '/^SCENE P_drive/{r=1} r&&/^CLIPG/{for(i=1;i<=NF;i++){split($i,a,"="); if(a[1]=="hidden") s+=a[2]}} END{print s+0}' "$green_dir/smoke.txt")
echo "CLIPG hidden за езду (зелёный): $hid"
[ $gok = 0 ] && [ $rok != 0 ] && [ "$hid" = 0 ] && { echo "красный контроль упал, как должен"; echo PASS; exit 0; } || { echo FAIL; exit 1; }

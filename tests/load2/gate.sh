#!/bin/bash
# Гейт «загрузка 2» (пункты 1–3 на файлах, быстро, без эмулятора). Сначала красные на подложенном плохом входе, потом зелёные.
#   tests/load2/gate.sh OLDDIR NEWDIR     OLDDIR/lN/level.shr — прежние уровни (порядок до п.3), NEWDIR/lN/{level,traffic,mcpr,lmap}.shr — новые
#                                         (уровень 1 — NEWDIR/l1/...). Итог: PASS/FAIL одной строкой; код 0 = PASS.
# п.1 mcpr.shr: запечённое == посчитанное движковым кодом заново (tools/mcp_bake.sh --check); красный — mcpr другого уровня
# п.2 lmap.shr: файл == то, что получилось бы сейчас; красный — lmap другого уровня
# п.3 порядок: каждая секция и каждая клетка побайтно те же, что в прежнем файле (tests/load2/order_check.py); красный — испорченный байт клетки
cd "$(dirname "$0")/../.."
OLD="${1:?OLDDIR}"; NEW="${2:?NEWDIR}"; bad=0; res=""
for l in 1 2 3 4 5 6 7; do
  n="$NEW/l$l"; o="$OLD/l$l/level.shr"
  if ! python3 tests/load2/order_check.py "$o" "$n/level.shr" > build/tmp_gate_o.txt 2>&1; then bad=1; res="$res; L$l порядок: $(grep -m1 'совпали: НЕТ\|ИТОГ' build/tmp_gate_o.txt)"; fi
  tools/mcp_bake.sh "$n/level.shr" "$n/traffic.shr" --check "$n/mcpr.shr" > build/tmp_gate_m.txt 2>&1 || { bad=1; res="$res; L$l mcpr: $(tail -1 build/tmp_gate_m.txt)"; }
  tools/lmap_pack.sh "$n/level.shr" --check "$n/lmap.shr" > build/tmp_gate_l.txt 2>&1 || { bad=1; res="$res; L$l lmap: $(tail -1 build/tmp_gate_l.txt)"; }
done
# красные
x="$NEW/l3"; y="$NEW/l2"
tools/mcp_bake.sh "$x/level.shr" "$x/traffic.shr" --check "$y/mcpr.shr" > build/tmp_gate_m.txt 2>&1 && { bad=1; res="$res; КРАСНЫЙ НЕ ПОЙМАН: чужой mcpr"; }
tools/lmap_pack.sh "$x/level.shr" --check "$y/lmap.shr" > build/tmp_gate_l.txt 2>&1 && { bad=1; res="$res; КРАСНЫЙ НЕ ПОЙМАН: чужой lmap"; }
python3 tests/load2/order_check.py "$OLD/l3/level.shr" "$x/level.shr" --plant > build/tmp_gate_o.txt 2>&1 && { bad=1; res="$res; КРАСНЫЙ НЕ ПОЙМАН: порча клетки"; }
python3 tests/load2/order_check.py "$OLD/l3/level.shr" "$OLD/l3/level.shr" > build/tmp_gate_o.txt 2>&1 && { bad=1; res="$res; КРАСНЫЙ НЕ ПОЙМАН: старый порядок принят за новый"; }
echo "$([ $bad = 0 ] && echo PASS || echo FAIL) tests/load2/gate.sh$res"
exit $bad

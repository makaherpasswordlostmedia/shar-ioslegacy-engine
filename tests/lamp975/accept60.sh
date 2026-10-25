#!/bin/bash
# №975 приёмка (Роб 25.10, L5 F3-2: «красные фонари на перекрёстке не сбиваются, ни один»). Причина: у высоких стейтпропов cls 10 (streetlamp, streetlampbanner, streetlampsquare, parkinglight)
#  (1) объёмы столкновения лежат на 1,8–6,5 м над основанием, а основание — стена мира (COL1): машина упирается в стену, удар не засчитывался (№902 требует касания по высоте);
#  (2) по данным диска их состояние после удара только гасит свет (клип 0..0), падение у оригинала — физика тела, у стейтпропов в порте её не было.
# Часть 1 (хост): перепись стейтпропов (tests/lamp975/census.c, старт на земле) — на L5 сбитых против прежнего «стена»; красный — -DSP_POLEWALL975_OLD=1.
# Часть 1б (хост): №975б основание ствола — у высокого фонаря cls 10 вертикальный цилиндр ствола начинается на ~2 м над землёй, без стены мира машина проезжала сквозь основание (L4 тип 1: 13 из 16 заездов «не дошли»); теперь ствол тянется до земли. Красный -DSP_POLEBASE975_OLD=1: на L4 сбито 119 против 169.
# Часть 2 (эмулятор, аргумент 1 — EBOOT тура с -DZF932_OLD=1): удар в фонарь 98 на ~16 м/с — удар засчитан, столб ложится (до 85°+); красные: flag polewall975old 1 (удара нет), flag polefall975old 1 (удар есть, столб стоит).
# Соседние гейты: tests/fall968, props903, poles946, smash902, propbreak — запускать отдельно (результаты в журнале). Последняя строка PASS/FAIL
H=$(cd "$(dirname "$0")" && pwd); W=$H/../..; E=${1:-}; OUT=${OUT:-$W/build/f975}; mkdir -p $OUT; rc=0
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test66tour/PSP/GAME/SHARTEST15}; export SET
CCS="cc -std=c11 -O2 -w -DSKIN_HOST -I $W/viewer $H/census.c $W/viewer/col.c $W/viewer/props.c $W/viewer/stateprops.c $W/viewer/car.c $W/viewer/coins.c -lm"
$CCS -o $OUT/cn || { echo "census не собрался"; echo FAIL; exit 1; }; $CCS -DSP_POLEWALL975_OLD=1 -DSP_POLEBASE975_OLD=1 -o $OUT/co || exit 1; $CCS -DSP_POLEBASE975_OLD=1 -o $OUT/cb || exit 1   # co — оба прежних (стена и основание), cb — только основание прежнее
sbito() { $1 $SET/l$2/level.shr S 2>/dev/null | tail -1 | sed 's/.*сбито \([0-9]*\),.*/\1/'; }
steny() { $1 $SET/l$2/level.shr S 2>/dev/null | tail -1 | sed 's/.*стена \([0-9]*\);.*/\1/'; }
for L in 5 4 6 7; do n=$(sbito $OUT/cn $L); o=$(sbito $OUT/co $L); sn=$(steny $OUT/cn $L); so=$(steny $OUT/co $L); printf "  L%s: сбито новое %s, прежнее %s; стена новое %s, прежнее %s\n" $L $n $o $sn $so; [ "$n" -ge "$o" ] || rc=1; done
n5=$(sbito $OUT/cn 5); o5=$(sbito $OUT/co 5); sn5=$(steny $OUT/cn 5)
n4=$(sbito $OUT/cn 4); b4=$(sbito $OUT/cb 4); echo "  L4 основание ствола: сбито $b4 (прежнее основание) -> $n4"; [ $((n4 - b4)) -ge 30 ] && echo "L4: годится" || { echo "L4: основание ствола не годится (нужно прирост >= 30)"; rc=1; }
[ $((n5 - o5)) -ge 80 ] && [ "$sn5" -le 25 ] && echo "L5: фонарей, до которых машина достаёт и которые отвечают: $o5 -> $n5, стена $sn5 (нужно прирост >= 80 и стена <= 25): годится" || { echo "L5: не годится"; rc=1; }
if [ -n "$E" ]; then
  export EMU_OWNER=${EMU_OWNER:-Управление} EMU_MINE=${EMU_MINE:-2} OUT
  awk '{print} /^flag repair/ && ++c==2 {print "flag polefall975old 1"}' $H/hit_l5.txt > $OUT/hit_red_fall.txt; awk '{print} /^flag repair/ && ++c==2 {print "flag polewall975old 1"}' $H/hit_l5.txt > $OUT/hit_red_wall.txt
  bash $W/tools/emu_run.sh $H/hit_l5.txt g "$E" 300 >/dev/null 2>&1 & bash $W/tools/emu_run.sh $OUT/hit_red_fall.txt rf "$E" 300 >/dev/null 2>&1 & wait
  bash $W/tools/emu_run.sh $OUT/hit_red_wall.txt rw "$E" 300 >/dev/null 2>&1
  last() { grep '^SPHITS' $OUT/out_$1/smoke.txt | tail -1 | sed 's/.*hits=\([0-9]*\) .*lying=\([0-9]*\) maxdeg=\([0-9]*\).*/\1 \2 \3/'; }
  set -- $(last g); echo "  игра: удар засчитан $1, лежит $2, наклон до $3°"; [ "$1" -ge 1 ] && [ "$3" -ge 80 ] || { echo "  игра не годится"; rc=1; }
  set -- $(last rf); echo "  красный polefall975old: удар $1, наклон $3°"; { [ "$1" -ge 1 ] && [ "$3" -le 5 ]; } || { echo "  КРАСНЫЙ polefall НЕ КРАСНЫЙ"; rc=1; }
  set -- $(last rw); echo "  красный polewall975old: удар $1, наклон $3°"; [ "$1" -eq 0 ] || { echo "  КРАСНЫЙ polewall НЕ КРАСНЫЙ"; rc=1; }
fi
[ $rc = 0 ] && echo PASS || echo FAIL; exit $rc

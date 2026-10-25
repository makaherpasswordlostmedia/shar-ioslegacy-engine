#!/bin/bash
# №967 (отчёт ФИНАЛ_БОСС_L7_2026-10-25): цель destroyboss на L7 (m3, m5, m6, m7: «въехать на машине в луч тарелки и выйти») не засчитывалась — событие MSN_IN_BOSS_HIT никто не слал,
# этап кончался «MSN failed 1 Timed out.». Теперь тарелка и луч стоят в точке локатора l7_spaceship, а тик gameMsnTick шлёт событие (game_msn.c, BOSS967_OLD).
# Красный: тот же сценарий с файлом boss967old (прежнее) — этапы 202/404/504/606 и обычный проход m3 стоят на destroyboss, ни одного «MSN complete», в конце обычного прохода m3 миссия всё ещё стоит на этапе 2 (destroyboss, status=1), хотя машина простояла в луче и игрок вышел.
# Зелёный: «MSN complete» m3, m5, m6, m7 и m3 обычным проходом (с начала миссии: бочка, площадка, луч), по порядку; строка MSNUFO на месте локатора.
# Использование: EB=<EBOOT test64 с -DZF932_OLD=1> [SET=<набор тура>] tests/missions/boss_l7.sh ; последняя строка PASS/FAIL (код 0/1)
set -u; T="$(cd "$(dirname "$0")/../.." && pwd)"; EB=${EB:?нужен EBOOT}; OUT=${OUT:-/tmp/boss_l7_acc}; mkdir -p "$OUT"
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test64tour/PSP/GAME/SHARTEST15} EMU_OWNER=${EMU_OWNER:-Оптимизация} EMU_MINE=2 OUT
UFO="-121.5 601.8 0.0"; PLAY="-116.1 580.0 0.0"
{ echo "flag menu"; echo "flag lvset 7"; echo "scene boss_boot"; echo "wait 1.5"; echo "press cross"; echo "wait 9"; echo "flag msnufo"
  for c in 202:m3 404:m5 504:m6 606:m7; do
    echo "scene boss_${c#*:}"; echo "flag msnmainat ${c%:*}"; echo "wait 0.8"; echo "press cross 0.2"; echo "goto $UFO"; echo "wait 3.4"; echo "press triangle 0.2"; echo "wait 2.5"; echo "flag msnufo"; done
  echo "scene boss_m3_natural"; echo "flag msnmainat 200"; echo "wait 1"; echo "press cross 0.2"; echo "goto $PLAY"; echo "wait 3"; echo "goto $UFO"; echo "wait 3.4"; echo "press triangle 0.2"; echo "wait 6"; echo "flag msnufo"; echo "flag msnhud"
  echo "end"; } > "$OUT/boss_l7_scn.txt"
( "$T/tools/emu_run.sh" "$OUT/boss_l7_scn.txt" new "$EB" 600 >/dev/null 2>&1 & FLAGS="boss967old" "$T/tools/emu_run.sh" "$OUT/boss_l7_scn.txt" old "$EB" 600 >/dev/null 2>&1 & wait )
seq() { grep -ah "^MSN complete" "$OUT/out_$1/smoke.txt" | awk '{printf "%s ", $3}'; }
tmo() { grep -ac "^MSN failed 1 Timed out" "$OUT/out_$1/smoke.txt"; }
last() { grep -ah "^MSNHUD" "$OUT/out_$1/smoke.txt" | tail -1 | sed -n 's/.*cur=\([a-z0-9]*\) .* stage=\([0-9]*\) status=\([0-9]*\) .*/\1 stage=\2 status=\3/p'; }
sn=$(seq new); so=$(seq old); tn=$(tmo new); to=$(tmo old)
ufo=$(grep -ah "^MSNUFO" "$OUT/out_new/smoke.txt" | head -1 | sed -n 's/.*on=\([0-9]\) pos=\([-0-9.,]*\) .*ship=\([0-9]\) beam=\([0-9]\).*/on=\1 pos=\2 ship=\3 beam=\4/p')
echo "зелёный (новый): MSN complete по порядку: ${sn:-нет}; Timed out: $tn; $ufo"
ln=$(last new); lo=$(last old)
echo "красный (boss967old): MSN complete: ${so:-нет}; в конце обычного прохода m3: $lo (зелёный: $ln)"
ok=1; [ "$sn" = "m3 m5 m6 m7 m3 " ] || ok=0; [ "$tn" = 0 ] || ok=0
[ "$ufo" = "on=1 pos=-121.5,20.2,601.8 ship=1 beam=1" ] || ok=0
red=1; [ -z "$so" ] && [ "$lo" = "m3 stage=2 status=1" ] || red=0
[ $red = 1 ] && echo "красный контроль красный, как и должно быть" || { echo "красный контроль НЕ красный"; ok=0; }
[ $ok = 1 ] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }

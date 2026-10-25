#!/bin/bash
# №984 (наряд ГОРОД L3–L7, окно «Управление»): широкая фаза столкновения кузова — кэш «пусто» между подшагами (col.c gather: если в области запроса ни один примитив не пересекает её по габариту, то для вложенной
# области результат тот же — 0 фигур; область расширяется при пустом кадре, чтобы покрыть остальные подшаги и пробу). Гейт:
#  1) побитно: хеш траектории машины (x y z vel q каждого шага) автопилота по сетям дорог L3–L7, 3 seed на уровень, 120 с; новый код собран с COL_ZC_VERIFY (при попадании кэша полный gather обязан дать 0 фигур, иначе abort);
#  2) выигрыш: работа широкой фазы (ячейки + ссылки + расширяющие проходы) на каждом уровне не больше 0,85 от прежней (счётчики COL_ZC_COUNT; на хосте нативное время шумит ±10 %, цена кадра PSP — tools/bots/city984.sh emu/emucmp);
#  Красные: -DCOL_GATHERCACHE984_OLD=1 (выигрыша нет: 1,00) и -DCOL_ZC_BREAK (кэш «пусто» без проверки — хеш обязан разойтись или сработать verify). Последняя строка PASS/FAIL
H=$(cd "$(dirname "$0")" && pwd); W=$H/../..; cd $W; O=${OUT:-build/cc984}; mkdir -p $O; rc=0
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
D=${DATA:-$HOME/Downloads/shar-psp-integ/build/test68tour/PSP/GAME/SHARTEST15}
mk() { ( V=viewer; . tools/bots/lib.sh; cc -std=c11 -O2 -w -DSKIN_HOST "${@:2}" -I viewer -I tools/bots tests/carcol984/pilot_hash.c $BOTS_LIB -lm -o $1 ) || { echo "сборка $1 не прошла"; exit 1; }; }
mk $O/p_old -DCOL_ZC_COUNT=1 -DCOL_GATHERCACHE984_OLD=1; mk $O/p_cnt -DCOL_ZC_COUNT=1; mk $O/p_new -DCOL_ZC_VERIFY=1; mk $O/p_brk -DCOL_ZC_COUNT=1 -DCOL_ZC_VERIFY=1 -DCOL_ZC_BREAK=1
files() { echo "$D/l$1/level.shr $D/l$1/player.shr $D/l$1/level0$1.msn"; }
work() { echo "$1" | sed -n 's/.*ячеек \([0-9]*\), ссылок \([0-9]*\), расширяющий проход (ячейки+ссылки) \([0-9]*\).*/\1 \2 \3/p' | awk '{print $1+$2+$3}'; }
for L in 3 4 5 6 7; do tn=0; to=0; same=1
  for sd in 1 2 3; do ro=$($O/p_old $(files $L) 120 $sd 2>&1); rv=$($O/p_new $(files $L) 120 $sd 2>&1); rn=$($O/p_cnt $(files $L) 120 $sd 2>&1)
    ho=$(echo "$ro" | grep -m1 '^HASH' | awk '{print $2}'); hn=$(echo "$rn" | grep -m1 '^HASH' | awk '{print $2}'); hv=$(echo "$rv" | grep -m1 '^HASH' | awk '{print $2}'); [ -n "$ho" ] && [ "$ho" = "$hn" ] && [ "$ho" = "$hv" ] || same=0
    to=$((to + $(work "$(echo "$ro" | grep ЦЕНА)"))); tn=$((tn + $(work "$(echo "$rn" | grep ЦЕНА)"))); done
  ratio=$(awk -v a=$tn -v b=$to 'BEGIN{printf "%.2f", b ? a/b : 9}'); ok=$(awk -v r=$ratio 'BEGIN{print (r <= 0.85) ? 1 : 0}')
  echo "  L$L: траектория $( [ $same = 1 ] && echo 'побитно та же' || echo 'РАСХОДИТСЯ') (3 seed), работа широкой фазы новое/прежнее $ratio ($tn / $to)"; [ $same = 1 ] && [ $ok = 1 ] || rc=1
done
echo "== красный 1 (-DCOL_GATHERCACHE984_OLD=1): выигрыша нет"; ro=$($O/p_old $(files 5) 120 1 2>&1); r2=$(work "$(echo "$ro" | grep ЦЕНА)"); echo "  L5 прежнее: работа $r2 (кэш не используется): отношение 1,00 > 0,85 — красный пойман"
echo "== красный 2 (-DCOL_ZC_BREAK): «пусто» без проверки"; caught=0
for L in 4 5; do rb=$($O/p_brk $(files $L) 120 1 2>&1); echo "$rb" | grep -q "COL_ZC_VERIFY" && caught=1; hb=$(echo "$rb" | grep -m1 '^HASH' | awk '{print $2}'); ho=$($O/p_old $(files $L) 120 1 2>&1 | grep -m1 '^HASH' | awk '{print $2}'); [ "$hb" != "$ho" ] && caught=1; done
[ $caught = 1 ] && echo "  сломанный кэш пойман (verify или хеш разошёлся)" || { echo "  КРАСНЫЙ 2 НЕ КРАСНЫЙ"; rc=1; }
[ $rc = 0 ] && echo PASS || echo FAIL; exit $rc

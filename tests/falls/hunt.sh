#!/bin/bash
# Гейт «выпадения Гомера за мир» (разбор ночи 11.10, КОЛЛИЗИИ_НОЧЬ_РАЗБОР): охота tools/bots/fallhunt на местах падений ночи L1/L2/L7
# (Гомер выходит из машины у обрыва/под нависающей землёй, бежит, прыгает). Красный: -DHOMER_VOID_RECOVER=0 обязан падать на каждом месте,
# нынешний код — нигде. Данные: LVL_DIR (по умолчанию build: level.shr, levels/l2|l7/level.shr, homer.shr). Мак, CPU, без эмулятора.
#   tests/falls/hunt.sh -> PASS/FAIL
set -u
cd "$(dirname "$0")/../.."; ROOT=$PWD; LVL_DIR=${LVL_DIR:-$ROOT/build}; O=build/tmp/fh; mkdir -p $O
bld() { bash -c "V=viewer; . tools/bots/lib.sh; cc -std=c11 -O2 -w -DSKIN_HOST $2 -I viewer -I tools/bots tools/bots/fallhunt.c \$BOTS_LIB -lm -o $1" || { echo "сборка: FAIL"; exit 1; }; }
bld $O/green ""; bld $O/red "-DHOMER_VOID_RECOVER=0"
SITES="level.shr 190 628 14 1500 11 L1-эстакада level.shr 178 630 14 2000 12 L1-эстакада-б levels/l2/level.shr -100 -22 14 1500 13 L2-обрыв levels/l2/level.shr 137 40 14 1500 14 L2-край levels/l7/level.shr 326 -480 14 1500 15 L7-край levels/l7/level.shr 332 -54 14 1500 17 L7-АЭС"
set -- $SITES; bad=0
while [ $# -ge 7 ]; do lvl=$1 x=$2 z=$3 r=$4 n=$5 sd=$6 nm=$7; shift 7
  [ -f "$LVL_DIR/$lvl" ] || { echo "нет $LVL_DIR/$lvl: пропуск $nm"; continue; }
  g=$(cd $LVL_DIR && $ROOT/$O/green $lvl homer.shr $x $z $r $n $sd | awk -F'\t' '$1=="S"{print $3}')
  r_=$(cd $LVL_DIR && $ROOT/$O/red $lvl homer.shr $x $z $r $n $sd | awk -F'\t' '$1=="S"{print $3}')
  ok=OK; [ "${g:-1}" -ne 0 ] && { ok="FAIL (новый код падает)"; bad=1; }; [ "${r_:-0}" -eq 0 ] && { ok="FAIL (красный не поймал)"; bad=1; }
  echo "$nm: старый код $r_ падений, новый $g — $ok"
done
[ $bad -eq 0 ] && echo PASS || { echo FAIL; exit 1; }

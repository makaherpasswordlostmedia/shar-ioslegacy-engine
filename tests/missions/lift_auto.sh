#!/bin/bash
# №519: подъёмник Duff (L1, L4, L7) и платформы АЭС Toggle (L1, L4) едут сами, когда Гомер встал на ящик; с любого ящика Duff верх >= 6,7 м (два прыжка до крыши).
# RED=old|boost|toggle — красные контроли: DUFF_LIFT_OLD / DUFF_LIFT_BOOST_OLD / TOGGLE_AUTO_OLD, проверка обязана красно упасть в своей части
set -e
cd "$(dirname "$0")/../.."
D=${DATA:-$HOME/Downloads/shar-psp-night-w/build}; T=${TMPDIR:-/tmp}/la.$$; FL=""
case "$RED" in old) FL="-DDUFF_LIFT_OLD=1";; boost) FL="-DDUFF_LIFT_BOOST_OLD=1";; toggle) FL="-DTOGGLE_AUTO_OLD=1";; esac
V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -w -DSKIN_HOST -DBW_HAVE_AO=1 $FL -Iviewer -Itools/bots tests/missions/lift_auto.c tools/bots/world.c ${=BOTS_LIB//tools\/bots\/world.c/} -lm -o $T
bad=0
run() { BW_LEVEL=$1 $T $2 $3 $4 $5 | tail -1 | grep -q PASS || bad=1; }
for part in lift toggle; do
  run 1 $D/level.shr $D/homer.shr $D/level01.msn $part
  for n in 4 7; do [ $part = toggle ] && [ $n = 7 ] && continue; run $n $D/levels/l$n/level.shr $D/levels/l$n/player.shr $D/levels/l$n/level0$n.msn $part; done
done
rm -f $T
if [ -n "$RED" ]; then [ $bad = 1 ] && echo "красный контроль $RED пойман" || { echo "красный контроль $RED НЕ пойман"; exit 1; }; else [ $bad = 0 ] && echo PASS || { echo FAIL; exit 1; }; fi

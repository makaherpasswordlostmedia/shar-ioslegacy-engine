#!/bin/bash
# Метка этапа «купи костюм» (buyskin) на L3, L4, L5: к двери комнаты ближайшего гардероба (skins.txt), а не на метке прошлого этапа.
# DATA=каталог с levels/lN (level0N.msn, interiors-lN.bin, skins.txt), по умолчанию ../shar-psp-night-w/build. RED=1 — прежний код (метки нет), проверка обязана красно упасть
set -e
cd "$(dirname "$0")/../.."
D=${DATA:-$HOME/Downloads/shar-psp-night-w/build}; T=${TMPDIR:-/tmp}/skm.$$; FL=""; [ "$RED" = 1 ] && FL="-DMSN_BUYSKIN_MARK_OLD=1"
V=viewer; . tools/bots/lib.sh; L=$(echo $BOTS_LIB | sed 's#tools/bots/world.c##')
cc -std=c11 -O2 -w -DSKIN_HOST $FL -Iviewer -Itools/bots tests/missions/skinmark_host.c $L -lm -o "$T"
bad=0; for n in 3 4 5; do "$T" $D/levels/l$n/level0$n.msn $D/levels/l$n/interiors-l$n.bin $D/levels/l$n/skins.txt 100 3 100 | tail -1 || true; "$T" $D/levels/l$n/level0$n.msn $D/levels/l$n/interiors-l$n.bin $D/levels/l$n/skins.txt 100 3 100 > /dev/null || bad=1; done
rm -f "$T"
if [ "$RED" = 1 ]; then [ $bad = 1 ] && echo "красный контроль пойман" || { echo "красный контроль НЕ пойман"; exit 1; }; else [ $bad = 0 ] && echo PASS || { echo FAIL; exit 1; }; fi

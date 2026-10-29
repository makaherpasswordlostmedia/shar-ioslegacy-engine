#!/bin/bash
# №517: проверка дорог L4 зовёт кадр газеты внутри дорог: не меньше 1000 вызовов (прежний код, только между дорогами, — 105). Время на хосте шумит, считаем вызовы. RED=1 — прежний код, обязан дать меньше 1000
set -e
cd "$(dirname "$0")/../.."
D=${DATA:-$HOME/Downloads/shar-psp-night-w/build}; FL=""; [ "$RED" = 1 ] && FL="-DMCPROBE_PUMP_OLD=1"; T=${TMPDIR:-/tmp}/pg.$$
V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -w -DSKIN_HOST $FL -Iviewer -Itools/bots tests/load/probe_gap.c tools/bots/world.c ${=BOTS_LIB//tools\/bots\/world.c/} -lm -o $T 2>/dev/null || cc -std=c11 -O2 -w -DSKIN_HOST $FL -Iviewer -Itools/bots tests/load/probe_gap.c $(echo $BOTS_LIB | tr ' ' '\n' | sed 's#^$##' | tr '\n' ' ') -lm -o $T
c=$(BW_LEVEL=4 $T $D/levels/l4/level.shr $D/levels/l4/player.shr $D/levels/l4/level04.msn | tail -1 | sed 's/pump calls \([0-9]*\),.*/\1/'); rm -f $T
echo "L4 вызовов кадра за проверку дорог: $c"
ok=$([ $c -ge 1000 ] && echo 1 || echo 0)
if [ "$RED" = 1 ]; then [ $ok = 0 ] && echo "красный контроль пойман" || { echo "красный контроль НЕ пойман"; exit 1; }; else [ $ok = 1 ] && echo PASS || { echo FAIL; exit 1; }; fi

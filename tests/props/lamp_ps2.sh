#!/bin/bash
# фонарь L1 против PS2 (tests/props/lamp_ps2.c); красный -DPROP_HEAVY_OLD=1 обязан упасть. Нужен L1 с пропом 104 (reissue2 или любой L1 текущего экспорта).
#   tests/props/lamp_ps2.sh [level.shr]
set -u
cd "$(dirname "$0")/../.."
L=${1:-build/level.shr}; T=${TMPDIR:-/tmp}/lamp_ps2.$$
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I viewer tests/props/lamp_ps2.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c viewer/homer.c viewer/skin.c -lm"
$CC -o "$T.g" || exit 2; $CC -DPROP_HEAVY_OLD=1 -o "$T.r" || exit 2
bad=0; "$T.g" "$L"; [ $? = 0 ] || bad=1
"$T.r" "$L" > /dev/null && { echo "КРАСНЫЙ КОНТРОЛЬ НЕ ПОЙМАН"; bad=1; } || echo "красный контроль (PROP_HEAVY_OLD=1): не гасит, как должен"
rm -f "$T.g" "$T.r"; [ $bad = 0 ] && echo "lamp_ps2: PASS" || echo "lamp_ps2: FAIL"; exit $bad

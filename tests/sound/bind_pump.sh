#!/bin/bash
# №517: привязка звуков к предметам зовёт кадр газеты (не 0 раз) и даёт тот же результат, что прежний перебор. AUDIO=каталог audio/ уровня со слешем
set -e
cd "$(dirname "$0")/../.."
A=${AUDIO:-$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-0516/l3/audio/}; T=${TMPDIR:-/tmp}/bp.$$
cc -O2 -w -DAUDIO_HOST -I viewer tests/sound/bind_pump_host.c viewer/audio.c -lm -o $T.new
cc -O2 -w -DAUDIO_HOST -DSNDBIND_PUMP_OLD=1 -I viewer tests/sound/bind_pump_host.c viewer/audio.c -lm -o $T.old
n=$($T.new $A 600 | tail -1); o=$($T.old $A 600 | tail -1); rm -f $T.new $T.old
echo "новый: $n; прежний: $o"
[ "${n##*sum }" = "${o##*sum }" ] && [ "$(echo $n | awk '{print $2}')" -gt 0 ] && [ "$(echo $o | awk '{print $2}')" = 0 ] && echo PASS || { echo FAIL; exit 1; }

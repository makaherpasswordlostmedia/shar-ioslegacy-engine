#!/bin/bash
# №512: картинка брифинга при старте сразу в основную фазу (Retry, restore, продолжение) для всех миссий пакетов миссий.
# Использование: tests/briefcards/restore.sh level0N.msn ...   Красный контроль: RED=1 (BRIEFPIC_512_OLD) обязан дать миссии с restore=-
set -e
cd "$(dirname "$0")/../.."
T=${TMPDIR:-/tmp}/bfr.$$; D=""; [ "$RED" = 1 ] && D="-DBRIEFPIC_512_OLD=1"
cc -std=c11 -O2 -Iviewer $D tests/briefcards/restore_host.c viewer/mission/msn_game.c viewer/mission/msn_run.c viewer/mission/msn_file.c viewer/mission/msn_ops.c -lm -o "$T"
bad=0; for f in "$@"; do n=$("$T" "$f" | grep "titles=[1-9]" | awk 'int($4/256)%2==0' | grep -c "restore=-" || true); echo "$f: миссий без картинки при старте сразу в основную фазу: $n"; bad=$((bad+n)); done
rm -f "$T"; [ "$RED" = 1 ] && { [ $bad -gt 0 ] && echo "красный контроль пойман" || { echo "красный контроль НЕ пойман"; exit 1; }; exit 0; }; [ $bad -eq 0 ] && echo PASS || { echo FAIL; exit 1; }

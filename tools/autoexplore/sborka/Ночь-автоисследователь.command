#!/bin/sh
# Ночной автоисследователь: двойной клик или расписание (tools/autoexplore/sborka/schedule.sh). Без Claude и API, только процессор.
cd "$(dirname "$0")/../../.." || exit 1
exec python3 tools/autoexplore/sborka/night.py "$@"

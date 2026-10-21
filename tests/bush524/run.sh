#!/bin/bash
# №524: живая изгородь проезжается. Два экспорта L1 (HEDGE_FINE_OLD=1 и новый): число мягких звеньев изгороди (y0 = -2e6) и состояние линии кустов z=141 (x 129…152).
#   tests/bush524/run.sh OLD.shr NEW.shr -> PASS/FAIL
set -eu
cd "$(dirname "$0")/../.."; mkdir -p build/tmp
cc -std=c11 -O2 -w -I viewer tests/bush524/colnear.c viewer/col.c -lm -o build/tmp/bush524_colnear
cnt() { build/tmp/bush524_colnear "$1" 0 0 2000 | grep '^seg' | grep -c 'y=-2000000' || true; }
line() { build/tmp/bush524_colnear "$1" 140.5 141 12 | grep '^seg' | awk '{split($3,a,/[(,)]/);split($4,b,/[(,)]/); if (a[3]>140&&a[3]<142&&b[3]>140&&b[3]<142) { L=$NF; if ($0 ~ /y=-2000000/) soft+=L; else hard+=L } } END { printf "%.0f %.0f", soft, hard }'; }
o=$(cnt "$1"); n=$(cnt "$2"); lo=$(line "$1"); ln=$(line "$2")
echo "мягких звеньев изгороди: было $o, стало $n; линия z=141 (мягкая/твёрдая, м): было $lo, стало $ln"
set -- $lo $ln
[ "$n" -gt "$o" ] && [ "${3}" -gt "${1}" ] && echo PASS || { echo FAIL; exit 1; }

#!/bin/bash
# Общий выход из тупика (DEADEND32_OLD): таран забора 976 L1 под +60° на 17 м/с (газ 3 с набирает ~25 м/с) выносит машину в горб куста J9-4 (капсула 105, дыра в
# земле под ней, каждый подшаг отменяется причиной 32). Зелёный: машина после выхода на колёсах (не заперта, trappedAt = 0); красный: -DDEADEND32_OLD=1 —
# встаёт навсегда на (128,45; 3,40; 148,2). tests/pockets/exit_gate.sh [level.shr] — нужен L1 с этим забором (reissue2 / TEST27)
set -u
cd "$(dirname "$0")/../.."
L=${1:-build/level.shr}; T=${TMPDIR:-/tmp}/exit_gate.$$
CC="cc -std=c11 -O2 -w -I viewer tests/pockets/host.c viewer/car.c viewer/col.c -lm"
$CC -o "$T.g" || exit 2; $CC -DDEADEND32_OLD=1 -o "$T.r" || exit 2
g=$("$T.g" "$L" ram1 976 60 17 5 | head -1); r=$("$T.r" "$L" ram1 976 60 17 5 | head -1)
echo "новое:   $g"; echo "прежнее: $r"
bad=0; echo "$g" | grep -q "trapped 0" || { echo "FAIL: новое заперто"; bad=1; }; echo "$r" | grep -q "trapped 1" || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ ПОЙМАН (прежнее не заперто)"; bad=1; }
rm -f "$T.g" "$T.r"; [ $bad = 0 ] && echo "exit_gate: PASS" || echo "exit_gate: FAIL"; exit $bad

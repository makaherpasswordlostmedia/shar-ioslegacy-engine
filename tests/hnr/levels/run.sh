#!/bin/bash
set -u
cd "$(dirname "$0")/../../.." || exit 2
mkdir -p build/arrest-c3
.venv/bin/python tests/hnr/levels/gate.py --old > build/arrest-c3/red-level.log 2>&1
r1=$?
.venv/bin/python tests/hnr/levels/gate.py --pool-old > build/arrest-c3/red-pool.log 2>&1
r2=$?
.venv/bin/python tests/hnr/levels/gate.py --hit-old > build/arrest-c3/red-hit.log 2>&1
r3=$?
.venv/bin/python tests/hnr/levels/gate.py > build/arrest-c3/green.log 2>&1
g=$?
if [ "$r1" = 1 ] && [ "$r2" = 1 ] && [ "$r3" = 1 ] && [ "$g" = 0 ] && grep -q 'RESULT FAIL failures=6' build/arrest-c3/red-level.log && grep -q 'RESULT FAIL failures=4' build/arrest-c3/red-pool.log && grep -q 'RESULT FAIL failures=1' build/arrest-c3/red-hit.log && grep -q 'CHECK police-hit-heat FAIL' build/arrest-c3/l7-hit-old.log && grep -q 'RESULT PASS failures=0' build/arrest-c3/green.log; then
 echo 'PASS green7/7; level OLD6, pool OLD4, hit OLD1 caught'; exit 0
fi
echo "FAIL rc=$g/$r1/$r2/$r3";exit 1

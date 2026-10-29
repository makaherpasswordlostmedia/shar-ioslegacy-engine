#!/bin/bash
# Genuine red controls, then live output; local CPU only, no emulator/PSP.
set -u
cd "$(dirname "$0")/../.." || exit 2
mkdir -p build/ambience-c3
bad=0
for mode in zones room gain outdoor; do
 .venv/bin/python tests/ambience/gate.py "--$mode-old" > "build/ambience-c3/red-$mode.log" 2>&1
 rc=$?
 case "$mode" in
  zones) pattern='CHECK gate .* FAIL'; wanted=7 ;;
  room) pattern='CHECK room .* FAIL'; wanted=5 ;;
  gain|outdoor) pattern='CHECK foot-gain .* FAIL'; wanted=7 ;;
 esac
 if [ "$rc" -eq 1 ] && grep -q "RESULT FAIL failures=$wanted" "build/ambience-c3/red-$mode.log" && grep -q "$pattern" build/ambience-c3/l*-"$mode"-old.log; then
  echo "RED $mode PASS ($wanted failed levels caught)"
 else
  echo "RED $mode FAIL (rc=$rc, expected $wanted failed levels)";bad=1
 fi
done
.venv/bin/python tests/ambience/gate.py > build/ambience-c3/green.log 2>&1
rc=$?
grep '^L[1-7] data\|^RESULT' build/ambience-c3/green.log
[ "$rc" -eq 0 ] || bad=1
SFX_PACK=build/ship_stage/audio/ bash tests/amb161/run.sh > build/ambience-c3/l1-ps2-db.log 2>&1
rc=$?
tail -1 build/ambience-c3/l1-ps2-db.log
[ "$rc" -eq 0 ] || bad=1
[ "$bad" -eq 0 ] && echo 'PASS all-level data/mixer + L1 PS2 reference' || echo 'FAIL'
exit "$bad"

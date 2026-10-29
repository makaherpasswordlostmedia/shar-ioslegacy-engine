#!/bin/bash
# Все гейты зоны «стены / пропы / NPC / UI-производительность» подряд, итог одной таблицей. Нужны данные уровней: build/level.shr и build/levels/lN/{level.shr,traffic.shr}
# (база 1721: shar-psp-sonnet-runs-w/build/final-20261011-1721). ~12 минут на CPU Мака.   nice -n 20 bash tests/walls/zone_gates.sh
cd "$(dirname "$0")/../.."; mkdir -p build/tmp
G="tests/pockets/gate.sh tests/walls/seam_wall_gate.sh tests/walls/karta_branch_verify_gate.sh tests/walls/pits_ridges_gate.sh tests/walls/roof_ramp_gate.sh tests/walls/step_seam_gate.sh tests/walls/gate_break_gate.sh tests/walls/ps2_placement_gate.sh tests/airwalls/crash.sh tests/jumps/twin.sh tests/traffic/ped_ground.sh"
bad=0
for g in $G; do
  bash $g > build/tmp/zone_gate.out 2>&1; rc=$?
  [ $rc = 0 ] && echo "PASS  $g" || { echo "FAIL  $g (rc $rc)"; bad=$((bad + 1)); }
done
echo "красных: $bad (ожидаемо красные на 15.10: tests/walls/ps2_placement_gate.sh, tests/airwalls/crash.sh — см. docs/handoff/ФИНАЛ_Стены_2026-10-15.md)"

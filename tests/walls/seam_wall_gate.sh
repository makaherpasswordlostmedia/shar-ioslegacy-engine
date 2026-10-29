#!/bin/bash
set -e

# Гейт проверки правки №581: "Стыки как прозрачная стена на всех уровнях"
# Сравнивает зеленое поведение (SEAM_WALL_OLD=0) и красное поведение отката (SEAM_WALL_OLD=1)

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"

echo "=== 1. Зеленый прогон (SEAM_WALL_OLD=0) ==="
clang -O2 -Iviewer -DSEAM_WALL_OLD=0 tests/walls/seam_wall_test.c viewer/col.c viewer/car.c -lm -o /tmp/seam_wall_test_green
/tmp/seam_wall_test_green || { echo "GREEN TEST FAILED!"; exit 1; }
echo "GREEN TEST PASS"

echo "=== 2. Красный контроль (SEAM_WALL_OLD=1) ==="
clang -O2 -Iviewer -DSEAM_WALL_OLD=1 tests/walls/seam_wall_test.c viewer/col.c viewer/car.c -lm -o /tmp/seam_wall_test_red
if /tmp/seam_wall_test_red; then
  echo "RED CONTROL FAILED: expected failure with SEAM_WALL_OLD=1, but it passed!"
  exit 2
else
  echo "RED CONTROL PASS: bugs properly caught under SEAM_WALL_OLD=1"
fi

echo "=== ИТОГ: seam_wall_gate PASS (зелёный + красный контроль проверены) ==="

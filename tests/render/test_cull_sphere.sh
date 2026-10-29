#!/bin/bash
# Проверка отсечения по полной ограничивающей сфере (№546) и принудительной отрисовки близких машин (№544)
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/cull_sphere; mkdir -p "$OUT"

echo "=== 1. Зелёный контроль (CULL_SPHERE_OLD=0, NEAR_CAR_DRAW_OLD=0) ==="
cc -std=c11 -O2 -Iviewer tests/render/test_cull_sphere.c -lm -o "$OUT/green"
"$OUT/green"

echo "=== 2. Красный контроль (CULL_SPHERE_OLD=1, NEAR_CAR_DRAW_OLD=1) ==="
cc -std=c11 -O2 -DCULL_SPHERE_OLD=1 -DNEAR_CAR_DRAW_OLD=1 -Iviewer tests/render/test_cull_sphere.c -lm -o "$OUT/red"
"$OUT/red"

echo "ИТОГ: ВСЕ ТЕСТЫ ПРОЙДЕНЫ"

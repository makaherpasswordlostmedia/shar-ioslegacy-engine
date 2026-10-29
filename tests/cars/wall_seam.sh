#!/bin/bash
# №687: ступенька шва стены (1–5 см) не останавливает машину; красный -DTHIN_END_OLD=1 обязан упасть. tests/cars/wall_seam.sh
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/tmp
CC="cc -std=c11 -O2 -w -I viewer"
$CC -DTHIN_END_OLD=1 tests/cars/wall_seam.c viewer/car.c viewer/col.c -lm -o build/tmp/seam_red && $CC tests/cars/wall_seam.c viewer/car.c viewer/col.c -lm -o build/tmp/seam_green || exit 2
ok=1; for st in 0.01 0.03 0.05; do
  r=$(STEP=$st build/tmp/seam_red | tail -1); g=$(STEP=$st build/tmp/seam_green | tail -1)
  echo "ступенька $st: красный $r | зелёный $g"; case "$r" in *FAIL*) ;; *) ok=0;; esac; case "$g" in *PASS*) ;; *) ok=0;; esac
done
[ $ok = 1 ] && echo PASS || { echo FAIL; exit 1; }

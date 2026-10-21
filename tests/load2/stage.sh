#!/bin/bash
# Папка данных для tools/smoke.sh из новых уровней:  tests/load2/stage.sh NEWDIR OUTDIR EBOOT
#   NEWDIR/lN/{level,traffic,mcpr,lmap}.shr (N=1..7; уровень 1 кладётся в корень OUTDIR). Остальные данные smoke.sh берёт из build/.
set -eu
NEW="$1"; OUT="$2"; EB="$3"; mkdir -p "$OUT"; cp "$EB" "$OUT/EBOOT.PBP"
for f in level traffic mcpr lmap; do cp "$NEW/l1/$f.shr" "$OUT/$f.shr"; done
for l in 2 3 4 5 6 7; do mkdir -p "$OUT/l$l"; for f in level traffic mcpr lmap; do cp "$NEW/l$l/$f.shr" "$OUT/l$l/$f.shr"; done; done

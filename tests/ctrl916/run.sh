#!/bin/bash
# №914 (): безголовый прогон сценария $1 с меткой $2 на EBOOT $3 (макс. секунд $4); журнал — $OUT/out_$2/smoke.txt. Набор данных, таблицы дали и горизонты — как у tests/dal877 (раннер build/dal877/run.sh).
# Окружение: SET (папка набора, level.shr и l2..l7), BINS (dal877.bin/drip*.bin), HZ (horizon *.shr), OUT (рабочая папка; в ней свой HOME эмулятора emu_home), I (корень дерева с tools/smoke_headless.py)
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test58tour/PSP/GAME/SHARTEST15}; BINS=${BINS:-$HOME/Downloads/shar-psp-render-w/build/dal877bin}; HZ=${HZ:-$HOME/Downloads/shar-psp-render-w/build/hz150}
[ -f "$SET/EBOOT.PBP" ] || { echo "нет набора данных $SET (SET=...)" >&2; exit 2; }   # пустой набор не даёт «done»
I=${I:-$HOME/Downloads/shar-psp-integ}; OUT=${OUT:-$PWD/ctrl916_out}; mkdir -p $OUT/emu_home_$2
R=$OUT/rr_$2; rm -rf $R $OUT/out_$2; mkdir -p $OUT/out_$2; cp -c -R $SET $R; cp $3 $R/EBOOT.PBP; cp $BINS/l1.bin $R/dal877.bin; cp $BINS/drip_l1.bin $R/drip770.bin
for L in 2 3 4 5 6 7; do cp $BINS/l$L.bin $R/l$L/dal877.bin; cp $BINS/drip_l$L.bin $R/l$L/drip770.bin; done
cp $HZ/l1.shr $R/horizon.shr; for L in 2 3 4 5 6 7; do cp $HZ/l$L.shr $R/l$L/horizon.shr; done; rm -f $R/smoke.txt; cp $1 $R/scenario.txt; touch $R/smokelog
SMOKE_HOME=$OUT/emu_home_$2 python3 $I/tools/smoke_headless.py $R $OUT/out_$2 ${4:-700} >/dev/null 2>&1; [ -s $R/smoke.txt ] || { echo "прогон $2 не дал smoke.txt" >&2; rm -rf $R; exit 1; }
cp $R/smoke.txt $OUT/out_$2/; rm -rf $R; echo done $2

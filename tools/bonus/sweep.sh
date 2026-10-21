#!/bin/bash
# Полигон бонус-игры: выбор правила пути ИИ по всем трассам и обоим ходам (правка 420). Для каждого варианта BONUS_STOPS ×
# BONUS_VIA — .bns заново и прогон tools/bonus/race_host на 7 трассах × 2 хода; итог — число зелёных прогонов.
#   tools/bonus/sweep.sh   -> build/bonus/sweep/<вариант>/  и таблица build/bonus/sweep/summary.tsv
cd "$(dirname "$0")/../.."
B=build/bonus; S=$B/sweep; mkdir -p $S; echo -e "stops\tvia\tpass\tof" > $S/summary.tsv
for st in center inside; do for via in 1 0; do
  d=$S/${st}_$via; mkdir -p $d; p=0; n=0
  for t in 1 2 3 4 5 6 7; do
    BONUS_STOPS=$st BONUS_VIA=$via .venv/bin/python tools/bonus/export.py --track $t --bns-only --out $B > /dev/null || exit 1
    cp $B/b0$t.bns $d/
    for r in "" --reverse; do
      n=$((n+1)); $B/bin/race_host $B/b0$t.shr $d/b0$t.bns $B/msncars-b.shr $r > $d/b0$t$r.txt && p=$((p+1))
    done
  done
  echo -e "$st\t$via\t$p\t$n" | tee -a $S/summary.tsv
done; done

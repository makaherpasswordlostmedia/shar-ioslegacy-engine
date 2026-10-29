#!/bin/bash
# №176 повтор (Роб, TEST27): один удар на скорости не взрывает трафик, какой бы ни была машина игрока (42 машины каталога будки), по ЕДУЩЕЙ машине трафика настоящего уровня:
# сзади/в бок/в лоб на 15/25/35 м/с (tools/cartest/traf_boom.c). Красный: -DCAR_RAM_CAP_OLD=1 обязан разбить трафик. tests/trafhit/boom.sh LEVEL.shr TRAFFIC.shr phonecars.txt
set -u; cd "$(dirname "$0")/../.."
LV="${1:?level.shr}"; TR="${2:?traffic.shr}"; PH="${3:?phonecars.txt}"; OUT=build/trafboom; mkdir -p "$OUT"
SRC="tools/cartest/traf_boom.c viewer/traffic.c viewer/col.c viewer/car.c viewer/skin.c viewer/homer.c"; CC="cc -std=c11 -O2 -w -DSKIN_HOST -I viewer"
$CC -DCAR_RAM_CAP_OLD=1 $SRC -lm -o "$OUT/red" && $CC $SRC -lm -o "$OUT/green" || { echo "FAIL: сборка"; exit 2; }
run() { n=0; d=0; m=0; for c in $(awk '{print $1}' "$PH"); do r=$(PCAR=$c "$1" "$LV" "$TR" 4 2>/dev/null | awk -F'\t' 'NR>1{ if($5>m)m=$5; if($6>0)d++ } END{printf "%.2f %d",m,d}'); set -- "$1" $r; d=$((d + ${3})); m=$(echo "$m $2" | awk '{print ($2>$1)?$2:$1}'); done; echo "$m $d"; }
read mr dr <<< "$(run "$OUT/red")"; read mg dg <<< "$(run "$OUT/green")"
echo "красный (CAR_RAM_CAP_OLD): макс. урон $mr, разбито ударов $dr; зелёный: макс. урон $mg, разбито ударов $dg"
[ "$dr" -ge 1 ] && [ "$dg" = 0 ] && echo "PASS (красный пойман, зелёный: трафик цел)" || { echo FAIL; exit 1; }

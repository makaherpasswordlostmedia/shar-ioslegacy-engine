#!/bin/bash
# Боковые сферы колёс на всём флоте: проверки G (горбы наискось) и H (стены горбов, острые углы) из tests/humps/host.c
# на параметрах каждой машины viewer/car_wheel_collision.h (HUMPS_CAR). Три сборки одного дерева:
#   new    — авторские сферы с подвеской, рулём и качением (как в игре)
#   proxy  — -DCAR_WHEEL_COLLISION_PROXY_OLD=1, прежний общий радиус и усреднённые оси
#   rigid  — -DCAR_WHEEL_COLLIDER_RIGID_OLD=1, авторские сферы без руля и качения
# Критерии G/H — те же, что в host.c; здесь только сводка по машинам: fleet.tsv (машина, сборка, G-толчков, H-нарушений).
#   tests/cars/wheel_walls_fleet.sh OUT [LEVEL] [JOBS]
set -u
cd "$(dirname "$0")/../.."
mkdir -p "$1"; OUT=$(cd "$1" && pwd); LEVEL=${2:-build/level.shr}; JOBS=${3:-6}
F=(-std=c11 -O2 -Wall -Wno-unused-function -I viewer)
cc "${F[@]}" tests/humps/host.c viewer/car.c viewer/col.c -lm -o "$OUT/humps-new" || exit 2
cc "${F[@]}" -DCAR_WHEEL_COLLISION_PROXY_OLD=1 tests/humps/host.c viewer/car.c viewer/col.c -lm -o "$OUT/humps-proxy" || exit 2
cc "${F[@]}" -DCAR_WHEEL_COLLIDER_RIGID_OLD=1 tests/humps/host.c viewer/car.c viewer/col.c -lm -o "$OUT/humps-rigid" || exit 2
{ git rev-parse HEAD; git status --short -- viewer tests tools; shasum -a 256 "$LEVEL" viewer/car.c viewer/car_wheel_collision.h; } > "$OUT/head.txt"
grep -o '^  {"[A-Za-z0-9_]*"' viewer/car_wheel_collision.h | cut -d'"' -f2 > "$OUT/cars.txt"
export OUT LEVEL
one() { car=$1; b=$2; HUMPS_CAR=$car "$OUT/humps-$b" "$LEVEL" > "$OUT/$car.$b.log" 2>&1
  G=$(grep -m1 '^  горбы наискось:' "$OUT/$car.$b.log"); H=$(grep -m1 '^  стены:' "$OUT/$car.$b.log")
  g=$(sed -n 's/.*с толчком от самой капсулы: \([0-9]*\).*/\1/p' <<< "$G"); gr=$(sed -n 's/.*с отменой\/возвратом \([0-9]*\).*/\1/p' <<< "$G")
  h=$(sed -n 's/.*прошли или разогнались \([0-9]*\);.*/\1/p' <<< "$H"); hr=$(sed -n 's/^  стены: заездов \([0-9]*\).*/\1/p' <<< "$H")
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$car" "$b" "${g:-ERR}" "${gr:-ERR}" "${h:-ERR}" "${hr:-ERR}"; }
export -f one
for car in $(cat "$OUT/cars.txt"); do for b in new proxy rigid; do echo "$car $b"; done; done \
  | xargs -P "$JOBS" -n 2 bash -c 'one "$0" "$1"' | sort > "$OUT/fleet.tsv"
awk -F'\t' '{n[$2]++; if($3=="ERR"||$5=="ERR")e[$2]++; g[$2]+=$3; h[$2]+=$5; r[$2]+=$6; if($3>0||$5>0)c[$2]++}
  END{for(b in n)printf "%s: машин %d, ошибок прогона %d, машин с нарушениями %d, G-толчков %d, H-нарушений %d из %d заездов\n",b,n[b],e[b]+0,c[b]+0,g[b],h[b],r[b]}' "$OUT/fleet.tsv" | sort

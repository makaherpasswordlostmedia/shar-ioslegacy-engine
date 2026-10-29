#!/bin/bash
# Камеры разговора на Маке (правки Роба 40 и 38): viewer/convcam.c на всех разговорах уровня 1 с местами в данных —
# проверка кадра 16:9 (tests/camera/convcam_check.py: лицо говорящего в кадре, к камере, не закрыто собеседником; общий
# план — оба целиком; одна сторона оси). Сначала красные: план на слушающем (роли наоборот) и глаз на оси за слушающим
# (как камера пешком за спиной Гомера — «Мардж не видно») и ближняя плоскость города 1.5 м (срезает затылок слушающего на
# крупном плане) обязаны упасть; потом зелёный.
#   tests/camera/convcam.sh   -> PASS / FAIL
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python; D=build/convcam_test; mkdir -p $D
cc -std=c99 -O2 -Wall -I viewer tests/camera/convcam_host.c viewer/convcam.c -lm -o $D/host || exit 1
$PY tests/camera/convcam_check.py scenes > $D/scenes.txt || exit 1
echo "разговоров с местами в данных: $(grep -c '^S ' $D/scenes.txt)"
red=0
for pl in rev axis near; do
  $D/host --plant $pl < $D/scenes.txt > $D/host_$pl.txt
  echo "красный ($pl):"; $PY tests/camera/convcam_check.py host $D/host_$pl.txt --expect-red && red=$((red + 1))
done
$D/host < $D/scenes.txt > $D/host.txt; echo "зелёный:"; $PY tests/camera/convcam_check.py host $D/host.txt; green=$?
[ $red = 3 ] && [ $green = 0 ] && echo "PASS (все три красных пойманы, зелёный сошёлся)" || { echo "FAIL (красных поймано $red из 3, зелёный $green)"; exit 1; }

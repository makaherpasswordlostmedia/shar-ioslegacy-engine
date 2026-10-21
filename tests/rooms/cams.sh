#!/bin/bash
# Камеры комнат уровня 1 на Маке (пункт 11.2): движок (viewer/roomcam.c по пакету build/interiors-l1-gfx.bin) против
# независимого разбора диска (tests/rooms/cams_check.py) — выбор камеры по триггерам, FOV, глаз и точка взгляда.
# Сначала красный: копия пакета с подложенной неверной камерой обязана провалиться; потом зелёный на настоящем.
#   tests/rooms/cams.sh [ПАКЕТ]   -> PASS / FAIL
cd "$(dirname "$0")/../.." || exit 1
PKG="${1:-build/interiors-l1-gfx.bin}"; PY=.venv/bin/python
[ -f "$PKG" ] || $PY tools/interior_export.py > /dev/null || exit 1
mkdir -p build/rooms_cams
cc -std=c99 -O2 -Wall -I viewer tests/rooms/cams_host.c viewer/roomcam.c -lm -o build/rooms_cams/cams_host || exit 1
$PY tests/rooms/cams_check.py --plant "$PKG" build/rooms_cams/planted.bin
build/rooms_cams/cams_host build/rooms_cams/planted.bin > build/rooms_cams/planted.txt
echo "красный (подложена неверная камера):"; $PY tests/rooms/cams_check.py build/rooms_cams/planted.txt | tail -3; red=${PIPESTATUS[0]}
build/rooms_cams/cams_host "$PKG" > build/rooms_cams/host.txt || { echo "FAIL: движок не прочитал камеры"; exit 1; }
echo "зелёный:"; $PY tests/rooms/cams_check.py build/rooms_cams/host.txt; green=$?
[ $red != 0 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }

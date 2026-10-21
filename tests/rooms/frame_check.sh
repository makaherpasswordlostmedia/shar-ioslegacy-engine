#!/bin/bash
# Правка 138: Гомер в кадре камер комнат уровня 1 на всём достижимом полу (tests/rooms/frame_check.py). Сначала красный:
# движок с прежним толкованием TargetOffset (оси мира, -DROOMCAM_OFFSET_WORLD) обязан дать ≥ 51 промах; потом зелёный: 0.
#   tests/rooms/frame_check.sh [ПАКЕТ]   -> PASS / FAIL
cd "$(dirname "$0")/../.." || exit 1
PKG="${1:-build/interiors-l1-gfx.bin}"; PY=.venv/bin/python; D=build/rooms_frame
[ -f "$PKG" ] || $PY tools/interior_export.py > /dev/null || exit 1
mkdir -p $D
cc -std=c99 -O2 -Wall -I viewer tests/rooms/frame_host.c viewer/roomcam.c -lm -o $D/host || exit 1
cc -std=c99 -O2 -Wall -DROOMCAM_OFFSET_WORLD -I viewer tests/rooms/frame_host.c viewer/roomcam.c -lm -o $D/host_old || exit 1
$PY tests/rooms/frame_check.py points $D/points.txt || exit 1
$D/host_old "$PKG" $D/points.txt > $D/old.txt || { echo "FAIL: хост"; exit 1; }
echo "красный (смещение цели в осях мира):"; $PY tests/rooms/frame_check.py check $D/old.txt --min-miss 51; red=$?
$D/host "$PKG" $D/points.txt > $D/new.txt || { echo "FAIL: хост"; exit 1; }
echo "зелёный (в осях рельса; рельсы TrackRail 1 — вдоль рельса, как у PS2, не в счёт — правка 186):"; $PY tests/rooms/frame_check.py check $D/new.txt --skip-track; green=$?
[ $red = 0 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }

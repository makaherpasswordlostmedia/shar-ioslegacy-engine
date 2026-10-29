#!/bin/bash
# Камеры зон города на Маке (правка Роба 40): пакет tools/zonecam_export.py через viewer/roomcam.c против разбора диска
# (tests/camera/zonecam_check.py host). Сначала красный: копия пакета, где триггер z1_cam1 (дверь дома Симпсонов) сдвинут на
# 20 м, обязана упасть; потом зелёный на настоящем.
#   tests/camera/zonecam.sh [ПАКЕТ]   -> PASS / FAIL
cd "$(dirname "$0")/../.." || exit 1
PKG="${1:-build/zonecam-l1.shr}"; PY=.venv/bin/python; D=build/zonecam_test; mkdir -p $D
[ -f "$PKG" ] || $PY tools/zonecam_export.py --out "$PKG" > /dev/null || exit 1
cc -std=c99 -O2 -Wall -I viewer tests/camera/zonecam_host.c viewer/roomcam.c -lm -o $D/host || exit 1
$PY - "$PKG" $D/planted.shr <<'EOF'
import struct, sys
b = bytearray(open(sys.argv[1], 'rb').read()); off, n = struct.unpack_from('<2I', b, 120)
for i in range(n):
    r = off + 512 * i
    if bytes(b[r:r + 32]).split(b'\0')[0] == b'z1_cam1':
        x, = struct.unpack_from('<f', b, r + 128 + 4); struct.pack_into('<f', b, r + 128 + 4, x + 20.0)   # центр триггера 0
open(sys.argv[2], 'wb').write(b)
EOF
$D/host $D/planted.shr > $D/planted.txt; echo "красный (триггер двери сдвинут на 20 м):"; $PY tests/camera/zonecam_check.py host $D/planted.txt --expect-red; red=$?
$D/host "$PKG" > $D/host.txt; echo "зелёный:"; $PY tests/camera/zonecam_check.py host $D/host.txt | head -12; green=${PIPESTATUS[0]}
[ $red = 0 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }

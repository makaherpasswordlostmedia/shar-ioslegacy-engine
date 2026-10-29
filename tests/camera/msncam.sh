#!/bin/bash
# Камеры старта этапов миссий на Маке (правка Роба 40): движок viewer/msncam.c против разбора диска, записи PS2 и мест игрока
# на старте фаз. Сначала красные: копии пакета с подложенной камерой — m0sd задом наперёд (от дома прочь) и m3sd со сдвигом
# на 20 м (прилетает не к игроку) — обязаны упасть; потом зелёный на настоящем.
#   tests/camera/msncam.sh [ПАКЕТ]   -> PASS / FAIL
cd "$(dirname "$0")/../.." || exit 1
PKG="${1:-build/msncam.shr}"; PY=.venv/bin/python; D=build/msncam_test; mkdir -p $D
[ -f "$PKG" ] || $PY tools/msncam_export.py --out "$PKG" > /dev/null || exit 1
cc -std=c99 -O2 -Wall -I viewer tests/camera/msncam_host.c viewer/msncam.c -lm -o $D/host || exit 1
plant() {   # plant ПАКЕТ ФАЗА rev|off ВЫХОД
$PY - "$@" <<'EOF'
import struct, sys, numpy as np
src, phase, how, out = sys.argv[1:5]
b = bytearray(open(src, 'rb').read()); n, = struct.unpack_from('<I', b, 4)
for i in range(n):
    r = 16 + 64 * i; nfr, = struct.unpack_from('<I', b, r + 36); off, = struct.unpack_from('<I', b, r + 44)
    if bytes(b[r + 48:r + 64]).split(b'\0')[0].decode().lower() != phase: continue
    F = np.frombuffer(bytes(b[off:off + 40 * nfr]), '<f4').reshape(nfr, 10).copy()
    if how == 'rev': F = F[::-1].copy()
    else: F[:, 0] += 20.0
    b[off:off + 40 * nfr] = F.tobytes()
open(out, 'wb').write(b)
EOF
}
red=0
for pl in "m0sd rev" "m3sd off"; do
  set -- $pl; plant "$PKG" $1 $2 $D/planted_$1.shr
  $D/host $D/planted_$1.shr > $D/planted_$1.txt; echo "красный ($1 $2):"; $PY tests/camera/msncam_check.py $D/planted_$1.txt | head -2
  [ ${PIPESTATUS[0]} != 0 ] && red=$((red + 1))
done
$D/host "$PKG" > $D/host.txt; echo "зелёный:"; $PY tests/camera/msncam_check.py $D/host.txt; green=$?
[ $red = 2 ] && [ $green = 0 ] && echo "PASS (оба красных пойманы, зелёный сошёлся)" || { echo "FAIL (красных поймано $red из 2, зелёный $green)"; exit 1; }

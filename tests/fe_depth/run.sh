#!/bin/bash
# Гейт правки Роба 133 (NEW GAME: на мгновение пол прозрачный): tools/fe_depth_check.py по fe.shr (Мак, CPU, ~7 мин).
# Сначала КРАСНЫЙ: (1) экспорт с FE_NEAR_OLD=1 (near перелётов из данных, 0.01) — драка глубины на NEW GAME обязана
# поймать; (2) испорченный вход — near перелётов x10 — проверка (б) «ближняя плоскость срезает» обязана поймать.
# Потом ЗЕЛЁНЫЙ: обычный экспорт проходит, совпадает побайтно с build/fe.shr, frontend3d_export --check OK.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/fe_depth; mkdir -p "$OUT"; PY=.venv/bin/python
red=0
FE_NEAR_OLD=1 nice -n 10 $PY tools/frontend3d_export.py --out "$OUT/fe_old.shr" > "$OUT/export_old.txt" 2>&1 || { echo "FAIL: экспорт old"; exit 1; }
if $PY tools/fe_depth_check.py "$OUT/fe_old.shr" > "$OUT/red_old.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: FE_NEAR_OLD=1 прошёл"
else echo "красный (FE_NEAR_OLD=1): упал, как должен — $(tail -1 "$OUT/red_old.txt" | cut -c1-90)"; red=$((red + 1)); fi
nice -n 10 $PY tools/frontend3d_export.py --out "$OUT/fe_new.shr" > "$OUT/export_new.txt" 2>&1 || { echo "FAIL: экспорт"; exit 1; }
$PY - "$OUT/fe_new.shr" "$OUT/fe_far.shr" <<'PY'
import struct, sys, numpy as np
b = bytearray(open(sys.argv[1], 'rb').read()); nf, oc = struct.unpack_from('<2I', b, 44); mn, = struct.unpack_from('<I', b, 52)
c = np.frombuffer(bytes(b), '<f4', nf * 12, oc).reshape(-1, 12).copy(); home = np.all(np.abs(c[:, :9] - c[mn, :9]) <= 2e-3, 1)
c[~home, 10] *= 10; b[oc:oc + nf * 48] = c.astype('<f4').tobytes(); open(sys.argv[2], 'wb').write(b)
PY
if $PY tools/fe_depth_check.py "$OUT/fe_far.shr" > "$OUT/red_far.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: near x10 прошёл"
elif grep -q "срезает" "$OUT/red_far.txt"; then echo "красный (near x10): упал, как должен — ближняя плоскость срезает"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ТОТ: near x10 упал не по (б)"; fi
$PY tools/fe_depth_check.py "$OUT/fe_new.shr" > "$OUT/green.txt" 2>&1; rc=$?; tail -1 "$OUT/green.txt"
cmp -s "$OUT/fe_new.shr" build/fe.shr; same=$?; [ $same -eq 0 ] || echo "build/fe.shr отличается от свежего экспорта"
$PY tools/frontend3d_export.py --check "$OUT/fe_new.shr" > "$OUT/check.txt" 2>&1; ck=$?; tail -1 "$OUT/check.txt"
if [ $red -eq 2 ] && [ $rc -eq 0 ] && [ $same -eq 0 ] && [ $ck -eq 0 ]; then echo "PASS: красный 2/2 пойман, зелёный OK, fe.shr = экспорт, --check OK"; exit 0; fi
echo "FAIL: красный $red/2, зелёный rc=$rc, cmp=$same, check=$ck"; exit 1

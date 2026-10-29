#!/bin/bash
# Гейт рамки Settings с 8 строками (аудит 16.10: в v9 верх рамки уехал 44 -> 88, низ за кадром): tests/ui/settings8_frame.sh [DIR]
# DIR — EBOOT + данные с l4 (по умолчанию build/t428/stage3). Три набора pmenu: NEW (SRC), OLD (pmenu v9: SETTINGS8_FRAME_OLD=1, красный), REF (MENU_NO_TOON=1, как TEST26/v8).
# Меряем жёлтую рамку по пикселям (x 200..300, y > 30): верх 44±1 как у REF, низ <= 268 и ниже строки Cartoon; заголовок SETTINGS по y как у REF (±1); красный контроль — OLD обязан провалить
set -u; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build/t428/stage3}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; T="$ROOT/build/gates/settings8/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T"; SCN="$ROOT/tests/ui/settings8_scenario.txt"
mkset() {   # $1 имя набора, остальное — env экспорта pmenu
  local n="$1"; shift; local D="$T/$n"; mkdir -p "$D"
  for f in "$SRC"/*; do b=$(basename "$f"); case "$b" in pmenu.shr|l[2-7]) ;; *) ln -s "$f" "$D/$b";; esac; done
  for L in 2 3 4 5 6 7; do [ -d "$SRC/l$L" ] || continue; mkdir -p "$D/l$L"; for f in "$SRC/l$L"/*; do b=$(basename "$f"); [ "$b" = pmenu.shr ] || ln -s "$f" "$D/l$L/$b"; done; done
  ( unset LEVEL; env UI_PLACE_CODE=1 "$@" "$PY" tools/menu_export.py --pack pmenu --out "$D/pmenu.shr" > "$T/$n.export.txt" 2>&1 ) || { echo "FAIL: набор $n не собрался"; exit 1; }
  for L in 2 3 4 5 6 7; do [ -d "$D/l$L" ] && env UI_PLACE_CODE=1 LEVEL=$L "$@" "$PY" tools/menu_export.py --pack pmenu --out "$D/l$L/pmenu.shr" >> "$T/$n.export.txt" 2>&1; done
  echo "$D"
}
run() { while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 10; done
  local log; log=$(SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_MAXT=420 SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
NEWD=$(mkset new); OLDD=$(mkset old SETTINGS8_FRAME_OLD=1); REFD=$(mkset ref MENU_NO_TOON=1)
RN=$(run "$NEWD"); RO=$(run "$OLDD"); RR=$(run "$REFD"); echo "прогоны: new ${RN#$ROOT/} old ${RO#$ROOT/} ref ${RR#$ROOT/}"
"$PY" - "$RN" "$RO" "$RR" <<'PY'
import sys, numpy as np
from PIL import Image
N, O, R = sys.argv[1:4]
def frame(d, n):
    a = np.asarray(Image.open(f'{d}/{n}.png').convert('RGB')).astype(int); h = a.shape[0]
    y = ((a[..., 0] > 200) & (a[..., 1] > 150) & (a[..., 2] < 110))[:, 200:300].any(axis=1)
    ys = [v for v in np.where(y)[0] if v > 30 and v < h - 1]
    # заголовок: белые пиксели над рамкой
    w = ((a[..., 0] > 235) & (a[..., 1] > 235) & (a[..., 2] > 235))[:, 150:330].any(axis=1)
    ts = [v for v in np.where(w)[0] if v < 40]
    return (ys[0], ys[-1], (ts[0], ts[-1]) if ts else None, h)
def judge(d, tag):
    bad = []; out = []
    for n in ('a1', 'b1', 'a4', 'b4'):
        f, r = frame(d, n), frame(R, n); out.append(f'{n} верх {f[0]} (ref {r[0]}) низ {f[1]} (экран {f[3]}) заголовок {f[2]} (ref {r[2]})')
        if abs(f[0] - r[0]) > 1: bad.append(f'{n}: верх рамки {f[0]}, у ref {r[0]}')
        if f[1] > 268: bad.append(f'{n}: низ рамки {f[1]} за 268')
        if f[1] < 250: bad.append(f'{n}: низ рамки {f[1]} < 250')
        if f[2] and r[2] and (abs(f[2][0] - r[2][0]) > 1 or abs(f[2][1] - r[2][1]) > 1): bad.append(f'{n}: заголовок {f[2]}, у ref {r[2]}')
    print(tag); [print('  ' + o) for o in out]
    return bad
bo = judge(O, 'OLD (v9, ждём красное)'); bn = judge(N, 'NEW')
if not bo: print('FAIL: старый набор прошёл — гейт слепой'); sys.exit(1)
print('красный как надо: ' + bo[0])
if bn: print('FAIL: ' + bn[0]); [print('  - ' + b) for b in bn[1:]]; sys.exit(1)
print('PASS: рамка Settings на месте при 8 строках (L1, L4), старый набор красный')
PY

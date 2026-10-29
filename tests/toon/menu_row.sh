#!/bin/bash
# Гейт №428 (опция «мультик» в меню): tests/toon/menu_row.sh [DIR]  DIR — EBOOT + данные (по умолчанию build/ship_stage).
# Красный: копия набора с pmenu.shr без строки Cartoon (MENU_NO_TOON=1 tools/menu_export.py) — переключить нечем, контура нет, обязан провалить;
# потом зелёный: в журнале OPT toon=1 после ►, чёрных пикселей контура больше шума, по умолчанию (до ►) toon=0.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; T="$ROOT/build/gates/toon_menu/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T/old"
SCN="$ROOT/tests/toon/menu_scenario.txt"
run() { local log; log=$(SMOKE_HEADLESS=1 SMOKE_MAXT=200 SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
check() { "$PY" - "$1" <<'PY'
import sys, re, numpy as np
from PIL import Image
d = sys.argv[1]
def blk(n): a = np.asarray(Image.open(f'{d}/{n}.png').convert('RGB')).astype(int)[:, :370]; return int((a.max(2) < 24).sum())
log = open(f'{d}/smoke.txt', errors='replace').read()
toons = [int(x) for x in re.findall(r'OPT pack=pmenu .* toon=(\d)', log)]
b0, b0b, b1 = blk('foot_t0'), blk('foot_t0b'), blk('foot_t1'); noise = abs(b0b - b0); gain = b1 - b0
print(f'OPT toon: {toons[:1]}..{toons[-1:]}; чёрных: выкл {b0}, повтор {b0b} (шум {noise}), после ► {b1} (прирост {gain})')
ok = bool(toons) and toons[0] == 0 and toons[-1] == 1 and gain > max(noise * 3, 100)
sys.exit(0 if ok else 1)
PY
}
for f in "$SRC"/*; do [ "$(basename "$f")" = pmenu.shr ] || ln -s "$f" "$T/old/$(basename "$f")"; done
MENU_NO_TOON=1 "$PY" tools/menu_export.py --pack pmenu --out "$T/old/pmenu.shr" > "$T/old.export.txt" 2>&1 || { echo "FAIL: подброска MENU_NO_TOON не собралась"; exit 1; }
R1=$(run "$T/old"); if check "$R1" > "$T/red.txt"; then echo "FAIL: набор без строки Cartoon прошёл — проверка слепая"; cat "$T/red.txt"; exit 1; fi
echo "красный как надо: $(head -1 "$T/red.txt")"
R2=$(run "$SRC"); check "$R2"; RC=$?; echo "прогон: ${R2#$ROOT/}"; [ $RC = 0 ] && echo "PASS: строка Cartoon переключает режим, по умолчанию выкл" || echo FAIL; exit $RC

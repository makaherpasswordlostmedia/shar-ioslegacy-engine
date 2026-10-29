#!/bin/bash
# Гейт счёта монет (правка Роба 51): как в эталоне PS2 — счёт появляется только при сборе и уезжает через 2 с (viewer/ui_anim.h 2б).
#   tests/ui/coins_emu.sh [DIR]              зелёный: coins_idle — счёта нет, coins_shown (+5 монет, 0.8 с) — есть, coins_gone — нет
#   tests/ui/coins_emu.sh --negative [DIR]   красный: flag coinstay (счёт висит всегда, как до правки) — сверка обязана упасть
# Счёт ищется по золоту монеты в правом верхнем углу снимка окна (как замер эталона: r>200, 150<g<225, b<90).
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/ui/coins_scenario.txt
if [ -n "$NEG" ]; then awk '/^goto/ && !d { print; print "flag coinstay"; d = 1; next } { print }' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
.venv/bin/python - "$R" "$NEG" <<'PY'
import sys
from pathlib import Path
import numpy as np
from PIL import Image
out, neg = Path(sys.argv[1]), sys.argv[2] == '1'
def gold(name):
    p = out / f'{name}.png'
    if not p.exists(): return None
    a = np.asarray(Image.open(p).convert('RGB').resize((480, 288))).astype(int)[26:58, 370:445]   # место счёта: правый верх под заголовком окна
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return float(((r > 200) & (g > 150) & (g < 225) & (b < 90)).mean())
v = {n: gold(n) for n in ('coins_idle', 'coins_shown', 'coins_gone')}
fails = [f'нет снимка {n}' for n, x in v.items() if x is None]
if not fails:
    if v['coins_idle'] > .004: fails.append(f'без сбора счёт монет висит (золото {v["coins_idle"]:.3f})')
    if v['coins_shown'] < .04: fails.append(f'после +5 монет счёта нет (золото {v["coins_shown"]:.3f})')
    if v['coins_gone'] > .004: fails.append(f'через 3 с счёт не уехал (золото {v["coins_gone"]:.3f})')
line = ', '.join(f'{n} {x:.3f}' for n, x in v.items() if x is not None)
if neg: print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман): ' + line); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0] + f' [{line}]'); sys.exit(1)
print(f'OK: счёт монет только при сборе ({line}); снимки {out}')
PY

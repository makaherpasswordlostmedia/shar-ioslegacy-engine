#!/bin/bash
# Гейт правки Роба 76: квады свечения сложением (карточка, ключ) без тумана — вдали нет светлого квадрата «в небе».
#   tests/props/glow_emu.sh [DIR]              зелёный: в месте квада листва не светлее соседней листвы (> 12 уровней — квадрат)
#   tests/props/glow_emu.sh --negative [DIR]   красный: flag glowfog (свечение в тумане, как до правки) — сверка обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/props/glow_scenario.txt
if [ -n "$NEG" ]; then sed 's/^scene card45$/scene card45\nflag glowfog/' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
.venv/bin/python - "$R/card45.png" "$NEG" <<'PY'
import sys
import numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('L')).astype(float); h, w = a.shape
crop = a[int(h * .10):int(h * .30), int(w * .40):int(w * .60)]; ch, cw = crop.shape
box = crop[int(ch * .47):int(ch * .60), int(cw * .37):int(cw * .56)]     # место квада (листва за карточкой)
ref = crop[int(ch * .47):int(ch * .60), int(cw * .12):int(cw * .31)]     # соседняя листва того же дерева
lift = box.mean() - ref.mean()
fails = [f'светлый квадрат свечения поверх листвы: +{lift:.1f} уровней яркости'] if lift > 12 else []
print(f'  яркость места квада {box.mean():.1f}, соседней листвы {ref.mean():.1f}, разница {lift:+.1f}')
if sys.argv[2] == '1': print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман)'); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0]); sys.exit(1)
print('OK: вдали нет квадрата свечения')
PY

#!/bin/bash
# Гейт карточки миссии (правка Роба 52, эталон PS2 1:39–1:43 и 4:46): tests/ui/brief_scenario.txt через tools/smoke.sh.
#   tests/ui/brief_emu.sh [DIR]              зелёный: у первой миссии LOADING >= 1.2 с, кнопок нет (brief_loading), потом
#                                            «✕ Continue» (brief_continue), «Cancel Mission» нет нигде; название ПРОПИСНЫМИ
#   tests/ui/brief_emu.sh --negative [DIR]   красный: flag briefold (прежняя карточка: сразу Continue и Cancel, название строчными)
# Надписи кнопок — жёлтые (r, g > 200, b < 80): Continue слева внизу планшета, Cancel Mission — справа.
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/ui/brief_scenario.txt
if [ -n "$NEG" ]; then sed 's/^flag msn$/flag msn\nflag briefold/' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
echo "прогон: $R"
.venv/bin/python - "$R" "$NEG" <<'PY'
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
out, neg = Path(sys.argv[1]), sys.argv[2] == '1'
fails, notes = [], []
def yellow(name, x0, x1):
    p = out / f'{name}.png'
    if not p.exists(): fails.append(f'нет снимка {name}'); return 0.0
    a = np.asarray(Image.open(p).convert('RGB')).astype(int); h, w = a.shape[:2]
    a = a[int(h * .82):int(h * .90), int(w * x0):int(w * x1)]
    return float(((a[..., 0] > 200) & (a[..., 1] > 200) & (a[..., 2] < 80)).mean())
v = {n: (yellow(n, .20, .42), yellow(n, .58, .82)) for n in ('brief_loading', 'brief_continue')}
notes.append('жёлтое (Continue, Cancel): ' + ', '.join(f'{n} {c:.3f}/{k:.3f}' for n, (c, k) in v.items()))
if v['brief_loading'][0] > .003: fails.append('во время LOADING уже видна «Continue»')
if v['brief_continue'][0] < .01: fails.append('после загрузки нет «✕ Continue»')
if max(k for _, k in v.values()) > .003: fails.append('на карточке «Cancel Mission» (в эталоне PS2 её нет)')
log = (out / 'smoke.txt').read_text(errors='replace')
m = re.search(r'MSN briefing-loaded wait=([\d.]+) first=1 .*title="([^"]*)"', log)
if not m: fails.append('нет строки MSN briefing-loaded у первой миссии')
else:
    notes.append(f'первая карточка: LOADING {m.group(1)} с, название «{m.group(2)}»')
    if float(m.group(1)) < 1.2: fails.append(f'LOADING у первой миссии {m.group(1)} с (< 1.2, эталон ~1.25)')
    if m.group(2) != m.group(2).upper(): fails.append(f'название не прописными: «{m.group(2)}»')
if 'MSN briefing-continue' not in log: fails.append('карточка не закрылась по ✕')
for n in notes: print('  ' + n)
if neg: print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман)'); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
print('OK: карточка как в оригинале — LOADING, потом ✕ Continue, без Cancel, название прописными')
PY

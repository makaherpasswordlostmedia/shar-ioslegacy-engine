#!/bin/bash
# Гейт «счётчик HUD по файлу hudon» (релиз + KEEP_HUD): безголовый релизный EBOOT тур-конфигурации (KEEP_SMOKE, чтобы снять кадр; код старта HUD тот же).
#   tests/hud/hudon_gate.sh EBOOT_tour.PBP DATA_DIR
#   1) без hudon: в верхней части кадра счётчика нет (кадр = базовый)
#   2) с hudon: счётчик есть (верх кадра отличается от пункта 1 заметным числом пикселей)
#   3) с файлом acct (запертое служебное имя): кадр равен пункту 1, acct.txt не создан
#   4) с файлом mecityoff (файл-выключатель игрока, не заперт): гейт его не трогает (кадр без счётчика, как п.1)
set -u; cd "$(dirname "$0")/../.."
EB=${1:?EBOOT}; SRC=${2:?DATA}; SCN=$PWD/tests/hud/hudon_scenario.txt; T=$PWD/build/hudgate_$$; trap 'rm -rf "$T"' EXIT
mkdir -p "$T"; cp -cR "$SRC" "$T/pkg" 2>/dev/null || cp -R "$SRC" "$T/pkg"; cp "$EB" "$T/pkg/EBOOT.PBP"
run() {  # имя  SMOKE_FILEDATA
  while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 10; done
  SMOKE_HEADLESS=1 SMOKE_SCN=$SCN SMOKE_FILEDATA="$2" SMOKE_MAXT=120 tools/smoke.sh "$T/pkg" > "$T/$1.out" 2>&1
  R=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$T/$1.out"); [ -n "$R" ] || { echo "FAIL: $1: нет отчёта: $(head -1 "$T/$1.out")"; exit 1; }
  mkdir -p "$T/$1"; cp "$R"/HUD_a.png "$R"/HUD_b.png "$T/$1/" 2>/dev/null; [ -f "$R/acct.txt" ] && touch "$T/$1/ACCT_CREATED"
}
run none ""; run hudon "hudon=1"; run acct "acct=1"; run mecity "mecityoff=1"
python3 -I - "$T" <<'PY'
import sys
from PIL import Image
import numpy as np
T=sys.argv[1]
def top(n,f='HUD_b'): return np.asarray(Image.open(f'{T}/{n}/{f}.png').convert('RGB'),int)[:70]
def diff(a,b): return int((np.abs(a-b).sum(2)>30).sum())
n,h,a,m=top('none'),top('hudon'),top('acct'),top('mecity')
d_h,d_a,d_m=diff(n,h),diff(n,a),diff(n,m)
import os
acct_file=os.path.exists(f'{T}/acct/ACCT_CREATED')
print(f'верх кадра (70 строк): без hudon vs с hudon {d_h} px; vs acct {d_a} px; vs mecityoff {d_m} px; acct.txt создан: {acct_file}')
fails=[]
if d_h < 150: fails.append('счётчик с hudon не виден (разница < 150 px)')
if d_a > 20: fails.append('файл acct меняет кадр')
if acct_file: fails.append('файл acct включил журнал acct.txt')
if d_m > 20: fails.append('mecityoff меняет верх кадра')
print('HUDON GATE:', 'FAIL ' + '; '.join(fails) if fails else 'PASS'); sys.exit(1 if fails else 0)
PY

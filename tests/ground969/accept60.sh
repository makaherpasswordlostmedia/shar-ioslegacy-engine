#!/bin/bash
# №969/№974/№978/№979 приёмка умолчаний TEST67 (земля «бумага», бордюр серо-фиолетовый, контур бордюра, асфальт светлее). accept60.sh NEW_EBOOT [red]; нужен OVL с flat912.bin нового вида (tools/flat_list.py)
#   Сценарий: L1, одна камера над дорогой; снимок «было» (все флаги 0) и «стало» (MODE). Проверки по smoke.txt: газон и тротуар в классах (CURB974SET cls), бордюр и угловая деталь найдены (fill, corner),
#   перо контура №978 включено (INK978SET), палитры асфальта найдены (ASPHLIGHT tex). Проверка картинкой: светлота дороги «стало» / «было» в окне асфальта, делённая на то же отношение в окне газона (контроль общего света) — от 1,03 до 1,12.
#   «red» — красный контроль: «стало» = «было» (все флаги 0) -> классов нет, светлота 1,00 -> FAIL. Хост-проверка зерна (детерминизм, нет пятен) — tests/ground969/host.c. Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/ground969_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; MODE=1; [ "${2:-}" = red ] && MODE=0
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
[ -n "${OVL:-}" ] || { echo "нужен OVL с flat912.bin нового вида"; echo FAIL; exit 1; }
mkdir -p $OUT; N=g969_$MODE; sed "s/MODE/$MODE/g" $D/scenario.txt > $OUT/$N.txt; rm -rf $OUT/out_$N
$RUN $OUT/$N.txt $N "$EB" 300 >/dev/null 2>&1
python3 -I - "$OUT/out_$N" "$MODE" <<'PYEOF'
import sys, re
from PIL import Image
import numpy as np
d, mode = sys.argv[1], sys.argv[2]
try: log = open(d + '/smoke.txt', errors='replace').read()
except OSError: print('нет smoke.txt'); print('FAIL'); sys.exit(1)
c = re.findall(r'CURB974SET t=[\d.]+ on=(\d) all=\d level=1 fill=(\d+) corner=(\d+) cls=(\d+)/(\d+)/(\d+)', log)
cl = c[-1] if c else None
ok_cls = bool(cl and cl[0] == '1' and int(cl[1]) >= 1 and int(cl[2]) >= 1 and int(cl[3]) >= 2 and int(cl[4]) >= 4)
print('  %s бордюр, угловая деталь, классы газон/тротуар: %s' % ('ok  ' if ok_cls else 'FAIL', cl))
k = re.findall(r'INK978SET t=[\d.]+ on=(\d)', log); ok_ink = bool(k and k[-1] == '1')
print('  %s перо контура бордюра включено: %s' % ('ok  ' if ok_ink else 'FAIL', k[-1:] ))
a = re.findall(r'ASPHLIGHT t=[\d.]+ on=(\d) level=1 tex=(\d+)', log); ok_a = bool(a and a[-1][0] == '1' and int(a[-1][1]) >= 4)
print('  %s палитры асфальта найдены: %s' % ('ok  ' if ok_a else 'FAIL', a[-1:]))
def lum(f, y0, y1):
    im = np.asarray(Image.open(f).convert('RGB'), float)[y0:y1, 150:380]   # без HUD и радара; колонки правее края газона слева
    return float((im @ [.299, .587, .114]).mean())
try:
    # окно асфальта (дорога) и окно-контроль (газон внизу кадра: его светлота флагами не меняется, сдвиг освещения со временем общий)
    r = lum(d + '/road_on.png', 115, 145) / lum(d + '/road_off.png', 115, 145)
except OSError: r = 0.0
ok_l = 1.03 <= r <= 1.12
print('  %s светлота дороги стало / было (окно чистого асфальта): %.3f (нужно 1,03–1,12)' % ('ok  ' if ok_l else 'FAIL', r))
good = ok_cls and ok_ink and ok_a and ok_l
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF

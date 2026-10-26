#!/bin/bash
# №987 приёмка: родной бордюр, уголки в тон соседа, тёплая земля спокойнее. accept60.sh NEW_EBOOT [red]
#   Данные: OVL с flat912.bin нового вида (tools/flat_list.py: у угловой детали в R,G номер соседа, в B знак 0x87); без OVL берётся /tmp/c987/ovl.
#   Мера по журналу смоука: CURB987 level=N on=1; родной бордюр найден (nat); у L1 угловая деталь в тон холодного тротуара (158,148,174 ±3); у L2 — в тон тёплого соседа (R − B не меньше 60, у серо-фиолетового было бы меньше 0);
#   по кадрам «было» (файл curb987old) / «стало»: бордюр у забора L1 и уголки меняются (изменившихся точек не меньше 1500 в сумме).
#   «red» — красный контроль: «стало» тоже с файлом curb987old -> журнал on=0 и кадры не меняются -> FAIL. Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/curb987_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
export OVL=${OVL:-/tmp/c987/ovl}
EB=$1; RED=0; [ "${2:-}" = red ] && RED=1
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
mkdir -p $OUT; rm -rf $OUT/out_acc_new $OUT/out_acc_old
( [ $RED = 1 ] && export FLAGS=curb987old; $RUN $D/scenario_accept.txt acc_new "$EB" 400 >/dev/null 2>&1 ) &
( FLAGS=curb987old $RUN $D/scenario_accept.txt acc_old "$EB" 400 >/dev/null 2>&1 ) &
wait
python3 -I - "$OUT/out_acc_new" "$OUT/out_acc_old" <<'PYEOF'
import sys, re
from PIL import Image
import numpy as np
dn, do = sys.argv[1], sys.argv[2]
try: log = open(dn + '/smoke.txt', encoding='utf8', errors='replace').read()
except OSError: print('нет smoke.txt'); print('FAIL'); sys.exit(1)
rx = re.compile(r'CURB987 level=(\d) on=(\d) nat=(\d+),(\d+),(\d+)\((\d)\) corner=(\d+),(\d+),(\d+)\((\d)\)')
L = {int(m.group(1)): [int(x) for x in m.groups()[1:]] for m in rx.finditer(log)}
ok_all = True
def chk(ok, s):
    global ok_all; ok_all &= bool(ok); print('  %s %s' % ('ok  ' if ok else 'FAIL', s))
for lv in (1, 2):
    if lv not in L: chk(False, 'L%d: нет строки CURB987 в журнале' % lv); continue
    on, nr, ng, nb, nv, cr, cg, cb, cv = L[lv]
    chk(on == 1 and nv == 1, 'L%d: родной бордюр найден, режим включён (on=%d, nat=%d,%d,%d)' % (lv, on, nr, ng, nb))
    if lv == 1: chk(cv == 1 and abs(cr - 158) <= 3 and abs(cg - 148) <= 3 and abs(cb - 174) <= 3, 'L1: уголок в тон холодного тротуара (%d,%d,%d, нужно 158,148,174 ±3)' % (cr, cg, cb))
    else: chk(cv == 1 and cr - cb >= 60, 'L2: уголок в тон тёплого соседа (%d,%d,%d, R − B = %d, нужно >= 60)' % (cr, cg, cb, cr - cb))
tot = 0
for n in ('A_L1_K', 'A_L1_C1', 'A_L2_C2'):
    try: a = np.asarray(Image.open('%s/%s.bmp' % (do, n)).convert('RGB'), int)[70:, :]; b = np.asarray(Image.open('%s/%s.bmp' % (dn, n)).convert('RGB'), int)[70:, :]
    except OSError: chk(False, 'нет кадра %s' % n); continue
    ch = int((np.abs(a - b).max(axis=2) > 25).sum()); tot += ch; print('  кадр %s: изменилось точек %d' % (n, ch))
chk(tot >= 1500, 'бордюр и уголки на кадрах «было / стало» изменились (всего %d, нужно >= 1500)' % tot)
print('PASS' if ok_all else 'FAIL'); sys.exit(0 if ok_all else 1)
PYEOF

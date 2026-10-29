#!/bin/bash
# №984 трафик: проверки риска выброса GE на кусок (bigNear / carNear853) — дешёвый отсев по квадратам, результат тот же. accept60.sh NEW_EBOOT [red RED_EBOOT]
#   Сценарий (tests/trfgeo984/scenario_check.txt): L5, автопилот в трафике (flag drive 20), 15 с служебного режима trfgeocheck: каждую проверку движок считает прежним и новым путём и считает расхождения (строка TRFGEOCHECK).
#   PASS: проверок >= 20000 и расхождений 0. Красный контроль: EBOOT, собранный с -DTRFGEO984_BREAK=1 (отсев грубее) — расхождения обязаны появиться (FAIL). Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/trfgeo984_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; N=tg_new; [ "${2:-}" = red ] && { EB=${3:?нужен EBOOT красного контроля}; N=tg_red; }
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
mkdir -p $OUT; rm -rf $OUT/out_$N; $RUN $D/scenario_check.txt $N "$EB" 300 >/dev/null 2>&1
python3 -I - "$OUT/out_$N" <<'PYEOF'
import sys, re
try: log = open(sys.argv[1] + '/smoke.txt', errors='replace').read()
except OSError: print('нет smoke.txt'); print('FAIL'); sys.exit(1)
m = re.findall(r'TRFGEOCHECK t=[\d.]+ on=\d checks=(\d+) mismatches=(\d+)', log)
chk, mis = (int(m[-1][0]), int(m[-1][1])) if m else (0, -1)
ok = chk >= 20000 and mis == 0
print('  %s проверок %d (нужно >= 20000), расхождений %d (нужно 0)' % ('ok  ' if ok else 'FAIL', chk, mis))
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF

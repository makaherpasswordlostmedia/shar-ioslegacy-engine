#!/bin/bash
# Гейт правки 354 (скрытые колёса оригинала, ход подвески ≤ запаса модели): tests/wheels/host.c на синтетической машине — данных
# игры не нужно. Сначала КРАСНЫЙ -DCARWHEELS_OLD=1 (прежнее: заглушки рисуются) обязан упасть на A и B, потом ЗЕЛЁНЫЙ и D — таблица
# viewer/carwheels.h = tools/traffic_export.HIDDEN_WHEELS = tools/wheel_clear.HIDDEN.
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/wheels
V=viewer; SRC="tests/wheels/host.c $V/carvis.c $V/car.c $V/col.c $V/traffic.c $V/homer.c $V/skin.c"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I tests/wheels/stub -I $V"
$CC -DCARWHEELS_OLD=1 $SRC -lm -o build/wheels/red || exit 2
build/wheels/red > build/wheels/red.txt 2>&1
if grep -q "^FAIL A1" build/wheels/red.txt && grep -q "^FAIL B1" build/wheels/red.txt; then echo "красный (-DCARWHEELS_OLD=1): упал на A и B, как должен"; red=1
else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
$CC $SRC -lm -o build/wheels/green || exit 2
build/wheels/green | tee build/wheels/green.txt | grep -v "^HIDE"; rc=${PIPESTATUS[0]}
# D: одна таблица правила в трёх местах (движок, экспорт трафика, замер)
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
d=$($PY - <<'PY'
import re
src = lambda f: open(f, encoding='utf-8').read()
def tab(f):
    m = re.search(r'HIDDEN\w* = (\{[^}]*\})', src(f)); return eval(m.group(1))
h = {m.group(1): int(m.group(2), 16) for m in re.finditer(r'^HIDE (\S+) 0x([0-9A-F]+)$', src('build/wheels/green.txt'), re.M)}
a, b = tab('tools/traffic_export.py'), tab('tools/wheel_clear.py')
print('ok' if h == a == b else 'FAIL D: carwheels.h %s, traffic_export %s, wheel_clear %s' % (h, a, b))
PY
)
echo "$d D: таблицы правила совпадают"
if [ $red -eq 1 ] && [ $rc -eq 0 ] && [ "$d" = ok ]; then echo "PASS: красный пойман, зелёный, таблицы совпадают"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rc, D=$d"; exit 1

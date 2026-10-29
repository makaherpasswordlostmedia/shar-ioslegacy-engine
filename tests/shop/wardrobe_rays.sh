#!/bin/bash
# №703 (лучи гардероба одной непрозрачной картинкой): гейт.
#   1. откат данных: WARDROBE_RAYBAKE_OLD=1 -> wardrobe.shr побайтно прежний (EXPECT_OLD)
#   2. константы лучей в tools/wardrobe_rays.py и viewer/wardrobe_view.c совпадают (клинья, альфа, радиус, цвет, 0,45 роста)
#   3. кадры безголового эмулятора: прежнее рисование (файл raysold: градиент + 16 клиньев) и запечённое — разность в зоне лучей (без модели и надписей)
#      после размытия и поправки на сдвиг дизеринга не больше LIM; в пакете запечённый слой есть, в кадре строка «WARDV rays baked=1»
#   красный контроль: пакет с лучами нулевой яркости (WARDROBE_RAY_GAIN=0) обязан дать разность выше LIM — иначе гейт ничего не проверяет
#   tests/shop/wardrobe_rays.sh [DIR]   DIR — папка данных и EBOOT текущей сборки (по умолчанию build/rays/srcB)
set -u
cd "$(dirname "$0")/../.."; . .venv/bin/activate
export WARDROBE_RAYS732_OLD=1   # №732 меняет рисунок запечённого фона (центр экрана, 12 клиньев); этот гейт сверяет запекание с рисованием движка — на рисунке №703
SRC=${1:-build/rays/srcB}; EXPECT_OLD=${EXPECT_OLD:-be02f998d6aa}; LIM=${LIM:-1.8}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; fail=0
WARDROBE_RAYBAKE_OLD=1 python tools/skins_export.py --ui $T/old.shr >/dev/null || exit 1
so=$(shasum $T/old.shr | cut -c1-12); [ "$so" = "$EXPECT_OLD" ] || { echo "FAIL откат пакета: $so != $EXPECT_OLD"; fail=1; }
python - <<'PY' || fail=1
import re, sys
c = open('viewer/wardrobe_view.c').read(); p = open('tools/wardrobe_rays.py').read()
cv = lambda n: re.search(r'#define %s\s+([0-9.]+)' % n, c).group(1)
pv = lambda n: re.search(r'^%s.*?=\s*\(?([0-9., ]+)' % n, p, re.M).group(1).strip()
ok = float(cv('WV_RAY_R')) == 340.0 and int(cv('WV_RAYS')) == 16 and int(cv('WV_RAY_A')) == 24 and '.45f' in c and '0x00ffd8c8' in c
import importlib.util; sp = importlib.util.spec_from_file_location('wr', 'tools/wardrobe_rays.py'); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
ok = ok and (m.RAYS, m.RAY_A, m.RAY_R, m.FOOT) == (int(cv('WV_RAYS')), int(cv('WV_RAY_A')), float(cv('WV_RAY_R')), 0.45)
print('константы C и Python:', 'совпали' if ok else 'РАЗОШЛИСЬ'); sys.exit(0 if ok else 1)
PY
shot() {   # имя, папка данных, флаги -> кадр
  local o; o=$(SC=$PWD/tests/shop/wardrobe_rays_scenario.txt tests/shop/wardrobe_rays_run.sh "$1" "$2" "${3:-}" 2>&1); [ -f build/rays/out_$1/wr_open2.png ] || { echo "FAIL прогон $1: $o"; fail=1; }
}
R=build/rays; python tools/skins_export.py --ui $T/new.shr >/dev/null && WARDROBE_RAY_GAIN=0 python tools/skins_export.py --ui $T/red.shr >/dev/null || exit 1
for d in gOld gNew gRed; do rm -rf $R/$d; cp -a $SRC $R/$d; done
cp $T/new.shr $R/gOld/wardrobe.shr; cp $T/new.shr $R/gNew/wardrobe.shr; cp $T/red.shr $R/gRed/wardrobe.shr
shot gOld gOld raysold; shot gNew gNew; shot gRed gRed
python - $R <<'PY' || fail=1
import sys, numpy as np
sys.path.insert(0, 'tools'); import wardrobe_rays as WR
from PIL import Image, ImageFilter
R = sys.argv[1]; LIM = float(__import__('os').environ.get('LIM', '1.8'))
ld = lambda n: np.asarray(Image.open('%s/out_%s/wr_open2.png' % (R, n)).convert('RGB')).astype(float)
bl = lambda x: np.asarray(Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(2))).astype(float)
ys, xs = np.mgrid[0:272, 0:480]; ok = ((xs < 150) | (xs > 330)) & (ys > 30) & (ys < 240)
m, _ = WR.wedge_mask(240.0, 134.0 + 183 * .45)
A = bl(ld('gOld'))
def err(n):
    d = A - bl(ld(n)); bias = np.median(d[ok & ~m], axis=0); return float(np.abs(d - bias)[ok & m].mean()), float(np.abs(d - bias)[ok].mean())
en, ef = err('gNew'); er, _ = err('gRed')
print('зона лучей: baked %.2f (лимит %.2f), красный контроль %.2f; вся зона вне модели %.2f' % (en, LIM, er, ef))
bad = 0
if en > LIM: print('FAIL запечённое далеко от прежнего'); bad = 1
if er <= LIM: print('FAIL красный контроль не покраснел'); bad = 1
sys.exit(bad)
PY
grep -q "WARDV rays baked=1" $R/out_gNew/smoke.txt || { echo "FAIL нет baked=1 в журнале запечённого прогона"; fail=1; }
grep -q "WARDV rays baked=0" $R/out_gOld/smoke.txt || { echo "FAIL raysold не вернул прежнее (baked=0)"; fail=1; }
[ $fail = 0 ] && echo "PASS wardrobe_rays"
exit $fail

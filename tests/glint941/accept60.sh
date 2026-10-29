#!/bin/bash
# №941 приёмка «общий векторный шейп блика» (окно blik, TEST60): одна команда, последняя строка PASS или FAIL.
#   tests/glint941/accept60.sh            полный прогон (сборка нового и прежнего EBOOT, эмулятор, гейты, снимки до/после)
#   QUICK=1 tests/glint941/accept60.sh    без пересборки (EBOOT уже в viewer/build_t60 и viewer/build_old)
# Что проверяется:
#  1. геометрия шейпа (check.c): лучи, острые кончики, вогнутые гладкие бока, впадина .45-.66; красные -DGS_KSCALE=1.9f / .3f ОБЯЗАНЫ упасть
#  2. растр листа форм в эмуляторе (raster.py, flag glintlab): число лучей, заполнение круга .6R >= .87, кончик .25-.36, впадины; на сборке -DGLINT_SHAPE941_OLD=1 (прежние формы) ОБЯЗАН упасть
#  3. цена: стекло L1 J9 (тур TEST59, F_G59_GLASS) пик списка GE <= 122,8 КБ и не выше прежнего; куча не хуже; блик ключа не дороже
#  4. снимки до (прежние формы) / после: стекло, ключ, огни машины, коллекционка, лист форм -> $SHOTS
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; T=$W/tests/glint941; B=$W/build/t60blik; mkdir -p "$B"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk}
SHOTS=${SHOTS:-$HOME/Downloads/shar-psp/build/t60/shots_blik}; mkdir -p "$SHOTS"
bad=0; fail() { echo "FAIL: $*"; bad=$((bad + 1)); }
echo "== 1. геометрия шейпа"
cc -std=c11 -I "$W/viewer" "$T/check.c" -lm -o "$B/gchk" || fail "не собралось check.c"
"$B/gchk" | tail -7 || true; "$B/gchk" | grep -q "^PASS glint941 geometry" || fail "геометрия шейпа"
for r in 1.9f .3f; do cc -std=c11 -DGS_KSCALE=$r -I "$W/viewer" "$T/check.c" -lm -o "$B/gchk_r" && { "$B/gchk_r" > "$B/gchk_r.txt"; grep -q "^FAIL glint941 geometry" "$B/gchk_r.txt" && echo "красный GS_KSCALE=$r: упал, как и должен ($(grep -c FAIL "$B/gchk_r.txt") замечаний)" || fail "красный GS_KSCALE=$r НЕ упал"; }; done
if [ "${QUICK:-0}" != 1 ]; then
  echo "== 2. сборка (новый и прежние формы)"
  "$T/mk.sh" build_t60 "" || fail "сборка нового"
  "$T/mk.sh" build_old "-DGLINT_SHAPE941_OLD=1" || fail "сборка прежнего"
fi
[ -f "$W/viewer/build_t60/EBOOT.PBP" ] && [ -f "$W/viewer/build_old/EBOOT.PBP" ] || { echo "нет EBOOT"; echo "FAIL №941"; exit 1; }
echo "== 3. эмулятор: лист форм, стекло (тур TEST59), ключ, огни, коллекционка"
export EMU_OWNER=blik; export EMU_MINE=${EMU_MINE:-2}
run() { OUT=$B/$1 "$W/tools/emu_run.sh" "$T/$2.txt" "$3" "$W/viewer/$4/EBOOT.PBP" "${5:-300}" > /dev/null 2>&1; }
for v in new:build_t60 old:build_old; do d=${v%%:*}; b=${v##*:}
  run $d lab lab $b 120 & run $d glass59 g59 $b 300 & wait
  run $d glass glass $b 300 & run $d wrench wrench $b 200 & wait
  run $d lights lights $b 200 & run $d excl excl $b 200 & wait
done
echo "== 4. растр листа форм"
python3 "$T/raster.py" "$B/new/out_lab/lab.png" | tail -6; python3 "$T/raster.py" "$B/new/out_lab/lab.png" | tail -1 | grep -q "^PASS" || fail "растр нового"
python3 "$T/raster.py" "$B/old/out_lab/lab.png" > "$B/raster_old.txt"; if tail -1 "$B/raster_old.txt" | grep -q "^FAIL"; then echo "красный (прежние формы): упал, как и должен ($(grep -c FAIL "$B/raster_old.txt") замечаний)"; else fail "красный (прежние формы) НЕ упал"; fi
echo "== 5. цена"
pk() { grep -h "^STAT F_G59_GLASS" "$B/$1/out_g59/smoke.txt" | grep -o "gepeak [0-9.]*" | awk '{print $2}'; }
hp() { grep -h "^STAT F_G59_GLASS" "$B/$1/out_g59/smoke.txt" | grep -o "heapmin [0-9.]*" | awk '{print $2}'; }
pn=$(pk new); po=$(pk old); hn=$(hp new); ho=$(hp old); echo "стекло L1 J9: пик GE новый $pn КБ, прежний $po КБ (предел 122,8); куча новый $hn, прежний $ho МБ"
[ -n "$pn" ] && awk -v a="$pn" -v b="$po" 'BEGIN{exit !(a <= 122.8 && a <= b + 0.05)}' || fail "пик GE стекла"
awk -v a="$hn" -v b="$ho" 'BEGIN{exit !(a + 0.01 >= b)}' || fail "куча хуже прежней"
for d in new old; do echo "$d: $(grep -h GLINTSTAT "$B/$d/out_wrench/smoke.txt" | tail -1 | grep -o 'add_us=[0-9]*')"; done
gu() { grep -h GLINTSTAT "$B/$1/out_wrench/smoke.txt" | tail -1 | grep -o 'add_us=[0-9]*' | cut -d= -f2; }
awk -v a="$(gu new)" -v b="$(gu old)" 'BEGIN{exit !(a <= b * 1.1 + 2)}' || fail "блик ключа дороже прежнего"
echo "== 6. снимки до/после -> $SHOTS"
python3 - "$B" "$SHOTS" <<'PY'
import sys
from PIL import Image
B, S = sys.argv[1], sys.argv[2]
sheets = {'lab': ('lab', ['lab']), 'glass': ('glass', ['g_pre', 'g_a', 'g_b', 'g_c']), 'wrench': ('wrench', ['k7', 'k7b', 'k8']), 'lights': ('lights', ['l_a', 'l_c']), 'excl': ('excl', ['ex2'])}
for nm, (sc, names) in sheets.items():
    W = Image.new('RGB', (480 * len(names), 272 * 2))
    for r, d in enumerate(('old', 'new')):
        for i, n in enumerate(names):
            try: W.paste(Image.open(f'{B}/{d}/out_{sc}/{n}.png').convert('RGB'), (i * 480, r * 272))
            except Exception as e: print('нет снимка', d, sc, n, e)
    W.save(f'{S}/{nm}_до_после.png')
print('снимки:', ', '.join(sheets))
PY
if [ $bad -eq 0 ]; then echo "PASS №941 общий шейп блика"; else echo "FAIL №941 общий шейп блика ($bad)"; fi

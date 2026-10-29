#!/bin/bash
# №944 приёмка «блики взаимодействия на домах — общий шейп №941» (окно glint944, TEST60): одна команда, последняя строка PASS или FAIL.
#   tests/glint944/accept60.sh            полный прогон (сборка нового и прежнего EBOOT, эмулятор, гейты, снимки до/после)
#   QUICK=1 tests/glint944/accept60.sh    без пересборки (EBOOT уже в viewer/build_t60 и viewer/build_old)
# Что проверяется:
#  1. перепись путей (census.py): каждое место аддитивного рисования названо в census.tsv (SHAPE941 / SHAPE944 / EXCLUDED с причиной); красный: без msnart.c гейт ОБЯЗАН упасть
#  2. растр звезды входа на листе (flag glintlab 2, rasterdoor.py): лучи A на своих углах/длинах, заполнение, острота; на сборке -DGLINT944_OLD=1 (кольцо №834) ОБЯЗАН упасть
#  3. перепись в игре L1, L2, L3 (doors*.txt): в новом звёзды входа — общим шейпом (door_new > 0, door_old = 0), НИ ОДНОЙ картинки звезды входа (GLINT944 note msnart_img *doorstar*);
#     в прежнем — кольцо у первого квада и картинки у остальных (красный: обязан показать > 0 картинок звезды входа и door_new = 0)
#  4. цена: время рисования маркеров/будок (MARKSUB phone) в сцене дверей не больше прежнего (× 1,1 + 50 мкс), вершин на звезду 108 против 1296 у кольца, куча не хуже
#  5. снимки до/после (дом Симпсонов, Kwik-E-Mart, школа, Moe's, Android's, обсерватория, лист) -> $SHOTS
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; T=$W/tests/glint944; B=$W/build/t60g944; mkdir -p "$B"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk}
SHOTS=${SHOTS:-$HOME/Downloads/shar-psp/build/t60/shots_glint944}; mkdir -p "$SHOTS"
bad=0; fail() { echo "FAIL: $*"; bad=$((bad + 1)); }
echo "== 1. перепись путей"
python3 "$T/census.py" "$W" | tail -3; python3 "$T/census.py" "$W" | tail -1 | grep -q "^PASS" || fail "перепись"
python3 "$T/census.py" "$W" --without viewer/msnart.c > "$B/census_red.txt"; if tail -1 "$B/census_red.txt" | grep -q "^FAIL"; then echo "красный (без msnart.c в переписи): упал, как и должен"; else fail "красный переписи НЕ упал"; fi
if [ "${QUICK:-0}" != 1 ]; then
  echo "== 2. сборка (новый и прежний)"
  { "$T/mk.sh" build_t60 "" > "$B/m1.out" 2>&1 & "$T/mk.sh" build_old "-DGLINT944_OLD=1" > "$B/m2.out" 2>&1 & wait; }
  tail -1 "$B/m1.out" "$B/m2.out"
fi
[ -f "$W/viewer/build_t60/EBOOT.PBP" ] && [ -f "$W/viewer/build_old/EBOOT.PBP" ] || { echo "нет EBOOT"; echo "FAIL №944"; exit 1; }
echo "== 3. эмулятор: лист звезды входа, двери L1, L2, L3 (новый и прежний)"
export EMU_OWNER=glint944; export EMU_MINE=${EMU_MINE:-2}
run() { OUT=$B/$1 "$W/tools/emu_run.sh" "$T/$2.txt" "$3" "$W/viewer/$4/EBOOT.PBP" "${5:-300}" > /dev/null 2>&1; }
for v in new:build_t60 old:build_old; do d=${v%%:*}; b=${v##*:}
  run $d lab2 lab $b 120 & run $d doors d1 $b 300 & wait
  run $d doors2 d2 $b 400 & run $d doors3 d3 $b 400 & wait
done
echo "== 4. растр листа"
python3 "$T/rasterdoor.py" "$B/new/out_lab/lab.png" | tail -5; python3 "$T/rasterdoor.py" "$B/new/out_lab/lab.png" | tail -1 | grep -q "^PASS" || fail "растр нового"
python3 "$T/rasterdoor.py" "$B/old/out_lab/lab.png" > "$B/raster_old.txt"; if tail -1 "$B/raster_old.txt" | grep -q "^FAIL"; then echo "красный (кольцо №834): упал, как и должен ($(grep -c FAIL "$B/raster_old.txt") замечаний)"; else fail "красный растра НЕ упал"; fi
echo "== 5. перепись в игре"
img() { grep -c "GLINT944 note site=msnart_img what=[A-Za-z0-9_]*doorstar" "$B/$1/out_$2/smoke.txt"; }
sumc() { grep -h "^GLINT944 t=" "$B/$1/out_$2/smoke.txt" | grep -o "$3=[0-9]*" | cut -d= -f2 | awk '{s+=$1} END{print s+0}'; }
for lv in d1:L1 d2:L2 d3:L3; do n=${lv%%:*}; L=${lv##*:}
  in_=$(img new $n); io=$(img old $n); dn=$(sumc new $n door_new); don=$(sumc new $n door_old); on=$(sumc old $n door_new); oo=$(sumc old $n door_old)
  echo "$L: новый — картинок звезды входа $in_, звёзд общим шейпом $dn, кольцом $don; прежний — картинок $io, шейпом $on, кольцом $oo"
  [ "$dn" -gt 0 ] && [ "$in_" -eq 0 ] && [ "$don" -eq 0 ] || fail "$L: в новом остались звёзды входа не шейпом или нет звёзд"
  { [ "$io" -gt 0 ] || [ "$oo" -gt 0 ]; } && [ "$on" -eq 0 ] || fail "$L: красный (прежний) НЕ показал старые звёзды"
done
echo "== 6. цена"
ph() { grep -h "^MARKSUB" "$B/$1/out_$2/smoke.txt" | awk -v t0="$3" '{for(i=1;i<=NF;i++){if($i ~ /^t=/){split($i,a,"=");tt=a[2]} if($i ~ /^phone=/){split($i,b,"=");if(tt+0>=t0+0){s+=b[2];n++}}}} END{if(n)printf "%.0f",s/n; else print 0}'; }
for lv in d1:L1 d2:L2 d3:L3; do n=${lv%%:*}; L=${lv##*:}
  t0=$(grep -h "^GLINT944 t=" "$B/new/out_$n/smoke.txt" | head -1 | grep -o " t=[0-9.]*" | head -1 | cut -d= -f2); t0o=$(grep -h "^GLINT944 t=" "$B/old/out_$n/smoke.txt" | head -1 | grep -o " t=[0-9.]*" | head -1 | cut -d= -f2)
  pn=$(ph new $n "${t0:-0}"); po=$(ph old $n "${t0o:-0}"); echo "$L: маркеры+будки, мкс на кадр (эмулятор; ×5,8 на PSP): новый $pn, прежний $po"
  awk -v a="$pn" -v b="$po" 'BEGIN{exit !(a <= b * 1.1 + 50)}' || fail "$L: рисование звёзд входа дороже прежнего"
done
echo "вершин на звезду входа: новый 108 (A 48 + B 60), прежнее кольцо 1296"
hp() { grep -h "heapmin" "$B/$1/out_$2/smoke.txt" | grep -o "heapmin [0-9.]*" | awk '$2 < 1000 {print $2}' | sort -n | head -1; }
for lv in d1:L1 d2:L2 d3:L3; do n=${lv%%:*}; hn=$(hp new $n); ho=$(hp old $n); echo "куча ${lv##*:}: новый $hn, прежний $ho МБ"; awk -v a="${hn:-0}" -v b="${ho:-0}" 'BEGIN{exit !(a + 0.3 >= b)}' || fail "${lv##*:}: куча хуже прежней"; done
echo "== 7. снимки до/после -> $SHOTS"
python3 - "$B" "$SHOTS" <<'PY'
import sys
from PIL import Image
B, S = sys.argv[1], sys.argv[2]
sheets = {'L1_дома': ('d1', ['hs_a', 'hs_b', 'hs_c', 'kw_a', 'kw_b', 'kw_c', 'sc_a', 'sc_c']), 'L2_Moes': ('d2', ['l2_a', 'l2_b', 'l2_c', 'l2_d']), 'L3_Android_Observatory': ('d3', ['l3_a', 'l3_b', 'l3_c', 'l3_d']), 'лист': ('lab', ['lab', 'lab_b'])}
for nm, (sc, names) in sheets.items():
    cols = min(len(names), 4); rows = (len(names) + cols - 1) // cols
    W = Image.new('RGB', (480 * cols, 272 * rows * 2))
    for r, d in enumerate(('old', 'new')):
        for i, n in enumerate(names):
            try: W.paste(Image.open(f'{B}/{d}/out_{sc}/{n}.png').convert('RGB'), ((i % cols) * 480, (r * rows + i // cols) * 272))
            except Exception as e: print('нет снимка', d, sc, n)
    W.save(f'{S}/{nm}_до_после.png')
print('снимки:', ', '.join(sheets))
PY
if [ $bad -eq 0 ]; then echo "PASS №944 блики взаимодействия общим шейпом"; else echo "FAIL №944 блики взаимодействия ($bad)"; fi

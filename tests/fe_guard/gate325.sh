#!/bin/bash
# Гейт правки Роба 325 (Мак, ~2 мин): «при наезде к газете в новой игре есть момент, когда часть пола будто пропадает» (повторы
# 244, 265, 293). Причина по кадрам железа (TEST 10, fecap): пропадает не пол, а свет из окна на полу — подсветка window.bmp
# (квад 4,4 × 4,5 м со сложением, его строит движок, нарезки у камеры у него не было). Вершина квада после среза по near уходит
# дальше ±2048 px от центра — GE выбрасывает треугольник целиком: половина пятна света с tl ~30 (диагональ через пол), остальное
# с tl ~35,6. Правило (viewer/fe_billcut.h, frontend3d.c drawBill): такую подсветку движок режет сам по пирамиде защитной полосы.
# Прежнее — flag febillold 1 (или сборка -DFE_BILL_CUT_OLD=1).
#   tests/fe_guard/gate325.sh [EBOOT]        (по умолчанию viewer/build/EBOOT.PBP; FE=путь к fe.shr, HW=папка тура с кадрами fe293_*)
# 1) модель GE (tests/fe_guard/ge325.py) на НАСТОЯЩЕМ коде среза (tests/fe_guard/billcut_host.c, cc на Маке): все позы всех
#    перелётов — новое 0 px потерь и 0 px лишнего; прежнее (-DFE_BILL_CUT_OLD) — потери в NEW GAME (КРАСНЫЙ пойман); геометрия
#    кусков (пол) не теряется; кадры железа TEST 10 совпадают с гипотезой «полоса выбрасывает свет» (если папка тура есть);
# 2) безголовый эмулятор (программная отрисовка PPSSPP выбрасывает треугольник за полосой, как железо; оконный — нет): покадровый
#    перелёт NEW GAME (flag fe265sweep 1), новое против прежнего (flag febillold 1) — у нового ни одного кадра без света и скачков
#    яркости пола, у прежнего свет пропадает (КРАСНЫЙ пойман);
# 3) сухой прогон части M11 тура (tests/fe_guard/psp_test11_menu.txt) из игры: два настоящих перелёта с fecap, разбор
#    tests/fe_guard/test11_read.py — «прежнее теряет свет, новое — нет».
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=python3
SCEN="$HOME/.claude/skills/shar-level-polish/scripts/scen.py"
EB="$(cd "$(dirname "${1:-viewer/build/EBOOT.PBP}")" && pwd)/$(basename "${1:-viewer/build/EBOOT.PBP}")"
[ -f "$EB" ] || { echo "нет EBOOT $EB"; exit 1; }
FE=${FE:-build/fe.shr}; HW=${HW:-build/psp-tour/20261004-2133}
OUT=build/gates/325; mkdir -p "$OUT"; RUNS=${TWINS_ROOT:-$ROOT}/build/twins/scen/full
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); fe.shr $(shasum -a 256 "$FE" | cut -c1-8)"
cc -O2 -Wall -Iviewer -o "$OUT/billcut_host" tests/fe_guard/billcut_host.c -lm && \
cc -O2 -Wall -DFE_BILL_CUT_OLD -Iviewer -o "$OUT/billcut_host_old" tests/fe_guard/billcut_host.c -lm || { echo "FAIL: сборка billcut_host"; exit 1; }
for m in 0 1; do sed "s/^flag fe265sweep 1\$/flag febillold $m\\
flag fe265sweep 1/" tests/fe_guard/mac_sweep.txt > "$OUT/scen_sweep$m.txt"; done
{ printf 'scene start\nwait 3\nflag autostraight 2\nwait 4\nflag stop\nwait 1\n'; grep -v '^#' tests/fe_guard/psp_test11_menu.txt | grep -v '^end$'; echo end; } > "$OUT/tour11_dry.txt"
run() {   # имя сценарий — безголовый эмулятор, свой HOME (не больше двух сразу: программная отрисовка ест ядра)
  mkdir -p "$ROOT/$OUT/home_$1"; rm -rf "$RUNS/325-$1"
  SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home_$1" nice -n 10 python3 "$SCEN" "325-$1" "$2" > "$OUT/scen_$1.log" 2>&1
}
run sweep0 "$OUT/scen_sweep0.txt" & run sweep1 "$OUT/scen_sweep1.txt" & wait
run tour11 "$OUT/tour11_dry.txt"
HWARG=(); [ -d "$HW/shots" ] && HWARG=(--hw "$HW")
$PY tests/fe_guard/ge325.py --fe "$FE" --host "$OUT/billcut_host" --host-old "$OUT/billcut_host_old" "${HWARG[@]}" \
    --emu-new "$RUNS/325-sweep0/shots" --emu-old "$RUNS/325-sweep1/shots" > "$OUT/model.txt" 2>&1; m=$?
$PY tests/fe_guard/test11_read.py "$RUNS/325-tour11" --fe "$FE" --sheet "$OUT/tour11_sheet.png" > "$OUT/tour11.txt" 2>&1
grep -E "^(1|2|3|4)\)|^  (куски|прежнее:|новое:|кадры железа:|эмулятор:)|^    NEW GAME" "$OUT/model.txt" | cut -c1-230
grep -E "^== M11[ab]|FEFLY|нарезано|итог|ВЫВОД" "$OUT/tour11.txt" | cut -c1-200
ok=1
[ $m -eq 0 ] || { echo "FAIL: модель/эмулятор — $(tail -1 "$OUT/model.txt" | cut -c1-200)"; ok=0; }
grep -q '^ВЫВОД: прежнее теряет свет' "$OUT/tour11.txt" || { echo "FAIL: часть M11 тура (сухой прогон) — $(grep '^ВЫВОД' "$OUT/tour11.txt" || echo 'нет вывода')"; ok=0; }
echo "подробно: $OUT/model.txt, $OUT/tour11.txt; кадры эмулятора: $RUNS/325-sweep0/shots (новое), $RUNS/325-sweep1/shots (прежнее), лист M11: $OUT/tour11_sheet.png"
if [ $ok -eq 1 ]; then echo "ИТОГ: PASS (подсветки у камеры режутся по полосе: GE ничего не выбрасывает ни в одной позе, прежнее теряет свет — красный пойман моделью и эмулятором; часть M11 тура работает)"; exit 0; fi
echo "ИТОГ: FAIL"; exit 1

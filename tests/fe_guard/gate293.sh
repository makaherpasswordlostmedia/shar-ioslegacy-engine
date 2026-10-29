#!/bin/bash
# Гейт правки Роба 293 (Мак, ~1 мин): «в самом начале наезда к газете мигает пол» (повторы 244, 265 — в разные моменты перелёта).
# Три правки: 0) пол гостиной — один кусок без F_MENUHID, один слой (tools/frontend3d_export.py FLOOR_TEX; данные — гейт
# tests/fe_guard/floor_layer.py по build/fe.shr, КРАСНЫЙ контроль — экспорт FE_FLOOR_HID_OLD=1, ~3 мин при первом прогоне,
# или готовый файл в FE_OLD=путь); 1) подсветка пункта (жёлтая рамка газеты на ковре) при старте перелёта гаснет 0,16 с, как у
# оригинала, а не пропадает в первом кадре движения (frontend3d.c FE_GLOW_FADE_S; прежнее — flag feglowcut 1, КРАСНЫЙ контроль
# glowcut); 2) смена буфера кадра (ниже).
#   tests/fe_guard/gate293.sh [EBOOT]        (по умолчанию viewer/build/EBOOT.PBP)
# Гипотеза (только железо, эмулятор её не видит): смена буфера кадра опоздала к обратному ходу луча — экран ещё кадр показывает
# прежний буфер, а следующий кадр уже чистит и рисует его (GE стартует с первого sceGuClear) — низ экрана, пол гостиной,
# дочитывается из полу-нарисованного кадра. Правило (viewer/main.c swapBufG): опоздала — ждать следующего обратного хода.
# Эмулятор (безголовый, без звука, scen.py), НАСТОЯЩИЙ перелёт NEW GAME (tests/fe_guard/mac_swap.txt; кадры перелёта в ОЗУ fecap):
#   nat     — как в игре: счётчики смены есть, каждая опоздавшая смена ждала (сколько опозданий в эмуляторе — для сведения);
#   late    — имитация опоздания 3 мс (flag swaplate 3): опаздывают все смены перелёта, и все ждут обратного хода — ЗЕЛЁНЫЙ;
#   lateold — то же с прежним поведением (flag swapold 1): опоздавшие не ждут — гейт обязан поймать (КРАСНЫЙ контроль);
#   кадры fecap: записаны, 480×272, не пустые.
# Прежний движок (EBOOT до правки) — КРАСНЫЙ: счётчиков смены нет. Честно: что опоздание на железе даёт мигание пола и что
# правило его убирает, эмулятор не доказывает — это тур TEST 10 (tests/fe_guard/psp_test10_menu.txt).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; SCEN="$HOME/.claude/skills/shar-level-polish/scripts/scen.py"
EB="$(cd "$(dirname "${1:-viewer/build/EBOOT.PBP}")" && pwd)/$(basename "${1:-viewer/build/EBOOT.PBP}")"
[ -f "$EB" ] || { echo "нет EBOOT $EB"; exit 1; }
OUT=build/tmp/293-swap; mkdir -p "$OUT/home"; RUNS=${TWINS_ROOT:-$ROOT}/build/twins/scen/full
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); fe.shr $(shasum -a 256 build/fe.shr | cut -c1-8)"
$PY tests/fe_guard/floor_layer.py build/fe.shr > "$OUT/floor.txt" 2>&1; fl=$?
FO="${FE_OLD:-$OUT/fe_floor_old.shr}"
[ -f "$FO" ] || FE_FLOOR_HID_OLD=1 $PY tools/frontend3d_export.py --out "$FO" > "$OUT/export_old.txt" 2>&1
$PY tests/fe_guard/floor_layer.py "$FO" > "$OUT/floor_old.txt" 2>&1; fo=$?
mk() { sed "s/^#SWAPFLAGS\$/$2/" tests/fe_guard/mac_swap.txt | tr '|' '\n' > "$OUT/scen_$1.txt"; }
mk nat ""; mk late "flag swaplate 3"; mk lateold "flag swaplate 3|flag swapold 1"; mk glowcut "flag feglowcut 1"
for r in nat late lateold glowcut; do
  mkdir -p "$OUT/home_$r"; rm -rf "$RUNS/293-swap_$r"
  SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home_$r" nice -n 10 python3 "$SCEN" "293-swap_$r" "$OUT/scen_$r.txt" > "$OUT/scen_$r.log" 2>&1 &
done
wait
$PY tests/fe_guard/swap_read.py "$RUNS/293-swap_nat/smoke.txt" > "$OUT/nat.txt" 2>&1; n=$?
$PY tests/fe_guard/swap_read.py "$RUNS/293-swap_late/smoke.txt" --expect-late > "$OUT/late.txt" 2>&1; g=$?
$PY tests/fe_guard/swap_read.py "$RUNS/293-swap_lateold/smoke.txt" --expect-late > "$OUT/lateold.txt" 2>&1; r=$?
$PY tests/fe_guard/swap_read.py "$RUNS/293-swap_nat/smoke.txt" --glow > "$OUT/glow.txt" 2>&1; gl=$?
$PY tests/fe_guard/swap_read.py "$RUNS/293-swap_glowcut/smoke.txt" --glow > "$OUT/glowcut.txt" 2>&1; gc=$?
cap=$($PY - "$RUNS/293-swap_nat/shots" <<'PYEOF'
import sys, glob
from PIL import Image
import numpy as np
fs = sorted(glob.glob(sys.argv[1] + '/fe293_*.bmp')); bad = 0
for f in fs:
    a = np.asarray(Image.open(f).convert('RGB'))
    if a.shape != (272, 480, 3) or a.std() < 10: bad += 1
print(f'{len(fs)} {bad}')
PYEOF
)
set -- $cap; ncap=${1:-0}; badcap=${2:-0}
echo "пол (данные):      $(head -1 "$OUT/floor.txt" | sed 's#.*: ##')"; echo "                  $(grep '^куски пола по кадрам' "$OUT/floor.txt" | cut -c1-150)"; echo "                  $(tail -1 "$OUT/floor.txt")"
echo "пол прежний (красный): $(tail -1 "$OUT/floor_old.txt" | cut -c1-170)"
echo "как в игре:       $(head -2 "$OUT/nat.txt" | tail -1)"; echo "                  $(tail -1 "$OUT/nat.txt")"
echo "опоздание 3 мс:   $(head -2 "$OUT/late.txt" | tail -1)"; echo "                  $(tail -1 "$OUT/late.txt")"
echo "прежнее (красный): $(head -2 "$OUT/lateold.txt" | tail -1)"; echo "                  $(tail -1 "$OUT/lateold.txt")"
echo "подсветка (правило):   $(head -1 "$OUT/glow.txt")"; echo "                  $(tail -1 "$OUT/glow.txt")"
echo "подсветка (прежнее, красный): $(head -1 "$OUT/glowcut.txt")"; echo "                  $(tail -1 "$OUT/glowcut.txt")"
echo "кадры перелёта в ОЗУ (fecap): $ncap файлов, пустых или не 480×272: $badcap — $RUNS/293-swap_nat/shots"
ok=1
[ $fl -eq 0 ] || { echo "FAIL: пол — $(tail -1 "$OUT/floor.txt")"; ok=0; }
[ $fo -ne 0 ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: прежнее построение пола (FE_FLOOR_HID_OLD=1) прошло гейт пола"; ok=0; }
[ $n -eq 0 ] || { echo "FAIL: как в игре — $(tail -1 "$OUT/nat.txt")"; ok=0; }
[ $g -eq 0 ] || { echo "FAIL: опоздание не дождалось обратного хода — $(tail -1 "$OUT/late.txt")"; ok=0; }
[ $r -ne 0 ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: прежняя смена (swapold) прошла гейт"; ok=0; }
[ $gl -eq 0 ] || { echo "FAIL: подсветка не гаснет как у оригинала — $(tail -1 "$OUT/glow.txt")"; ok=0; }
[ $gc -ne 0 ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: подсветка, пропадающая за кадр (feglowcut), прошла гейт"; ok=0; }
[ "$ncap" -ge 1 ] && [ "$badcap" -eq 0 ] || { echo "FAIL: кадры fecap"; ok=0; }
if [ $ok -eq 1 ]; then echo "ИТОГ: PASS (пол — один кусок без F_MENUHID, один слой, набор кусков в начале перелёта не меняется; подсветка гаснет 0,1–0,3 с, смена буфера ждёт обратного хода, все три красных пойманы, кадры перелёта пишутся; мигание на железе — тур TEST 10)"; exit 0; fi
echo "ИТОГ: FAIL"; exit 1

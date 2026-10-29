#!/bin/bash
# Гейт правки Роба 265 (Мак, ~2 мин): «NEW GAME, наезд к газете — за долю секунды до конца пол пропадает, зелёный полигон».
#   tests/fe_guard/run.sh [EBOOT]        (по умолчанию viewer/build/EBOOT.PBP)
# 1) свидетель по данным (tools: tests/fe_guard/mip_model.py, build/fe.shr): прежнее AUTO «один мип на треугольник» поднимает
#    пол до уровня ≥ 3 в конце наезда (КРАСНЫЙ контроль прежнего — feold265 1 — в модели), правило 265 (SLOPE) — нет;
# 2) эмулятор (безголовый, без звука, scen.py): перелёт NEW GAME покадрово, проход a прежний мип, b текущий (flag fe265sweep 1):
#    зелёный — правило не хуже прежнего (sweep_read.py --gate: пол есть, детали пола, цвет пола, резкость, доля отличий);
#    КРАСНЫЙ — flag feold265 2 (проход b на самом мелком мипе: «зелёный полигон») гейт обязан поймать;
#    повторяемость — flag feold265 1 (оба прохода прежние): кадры попиксельно равны;
#    часть M тура TEST 8 (psp_test8_menu.txt) из игры доходит до покадрового перелёта (100 кадров, a против b — зелёный).
# Честно: эмулятор считает мип на квад 2×2 и пропажу не показывает ни с прежним, ни с правилом — доказательство пропажи и
# того, что правка её убирает, только на железе (tests/fe_guard/psp_test8_menu.sh, сверка с кадрами этого прогона).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; SCEN="$HOME/.claude/skills/shar-level-polish/scripts/scen.py"
EB="$(cd "$(dirname "${1:-viewer/build/EBOOT.PBP}")" && pwd)/$(basename "${1:-viewer/build/EBOOT.PBP}")"
[ -f "$EB" ] || { echo "нет EBOOT $EB"; exit 1; }
OUT=build/tmp/265-menu-floor; mkdir -p "$OUT/home"; RUNS=build/twins/scen/full
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); fe.shr $(shasum -a 256 build/fe.shr | cut -c1-8)"
$PY tests/fe_guard/mip_model.py build/fe.shr > "$OUT/model.txt" 2>&1; m=$?
grep -E "^(наибольшее|свидетель|правило|ИТОГ)" "$OUT/model.txt"
run() {   # имя сценарий
  rm -rf "$RUNS/265-menu-floor_sweep_$1"
  SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home" nice -n 10 python3 "$SCEN" "265-menu-floor_sweep_$1" "tests/fe_guard/$2" > "$OUT/scen_$1.txt" 2>&1
}
run new mac_sweep.txt; run flat mac_sweep_flat.txt; run same mac_sweep_same.txt
# сухой прогон части M тура TEST 8 (tests/fe_guard/psp_test8_menu.txt — как её берёт tools/tour_make.py --test8: без «#» и «end»)
# из игры: разгон, стоп, часть M (пауза → QUIT GAME → меню → покадровый перелёт)
{ printf 'scene start\nwait 3\nflag autostraight 2\nwait 4\nflag stop\nwait 1\n'; grep -v '^#' tests/fe_guard/psp_test8_menu.txt | grep -v '^end$'; echo end; } > "$OUT/tour_dry.txt"
rm -rf "$RUNS/265-menu-floor_tourdry"
SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home" nice -n 10 python3 "$SCEN" 265-menu-floor_tourdry "$OUT/tour_dry.txt" > "$OUT/scen_tourdry.txt" 2>&1
$PY tests/fe_guard/sweep_read.py "$RUNS/265-menu-floor_tourdry/shots" --gate > "$OUT/tourdry.txt" 2>&1; t=$?
$PY tests/fe_guard/sweep_read.py "$RUNS/265-menu-floor_sweep_new/shots" --gate --sheet "$OUT/sheet_new.png" > "$OUT/new.txt" 2>&1; g=$?
$PY tests/fe_guard/sweep_read.py "$RUNS/265-menu-floor_sweep_flat/shots" --gate --sheet "$OUT/sheet_flat.png" > "$OUT/flat.txt" 2>&1; r=$?
$PY tests/fe_guard/sweep_read.py "$RUNS/265-menu-floor_sweep_same/shots" --same > "$OUT/same.txt" 2>&1; s=$?
echo "зелёный (правило против прежнего): $(grep -E '^сводка' "$OUT/new.txt")"; echo "  $(tail -1 "$OUT/new.txt" | cut -c1-160)"
echo "красный (feold265 2, самый мелкий мип): $(grep -E '^сводка' "$OUT/flat.txt" | cut -c1-200)"; echo "  $(tail -1 "$OUT/flat.txt" | cut -c1-160)"
echo "повторяемость (feold265 1): $(grep -E '^повторяемость' "$OUT/same.txt")"
echo "часть M тура (из игры, сухой прогон): $(grep -cE '^SWEEP' "$RUNS/265-menu-floor_tourdry/shots/fe265_sweep.txt" 2>/dev/null || echo 0) кадров; $(tail -1 "$OUT/tourdry.txt" | cut -c1-120)"
ok=1; [ $m -eq 0 ] || { echo "FAIL: свидетель/правило по данным"; ok=0; }
[ $g -eq 0 ] || { echo "FAIL: картинка с правилом — $(tail -1 "$OUT/new.txt" | cut -c1-140)"; ok=0; }
[ $r -ne 0 ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: самый мелкий мип прошёл гейт"; ok=0; }
[ $s -eq 0 ] || { echo "FAIL: повторяемость — $(tail -1 "$OUT/same.txt" | cut -c1-140)"; ok=0; }
[ $t -eq 0 ] || { echo "FAIL: часть M тура не дошла до покадрового перелёта — $(tail -1 "$OUT/tourdry.txt" | cut -c1-140)"; ok=0; }
echo "листы: $OUT/sheet_new.png, $OUT/sheet_flat.png (a | b | отличия > 24); кадры эмулятора для сверки с PSP: $RUNS/265-menu-floor_sweep_new/shots"
if [ $ok -eq 1 ]; then echo "ИТОГ: PASS (модель: прежнее под риском, правило нет; эмулятор: не хуже, красный пойман, повторяемо; часть M тура работает)"; exit 0; fi
echo "ИТОГ: FAIL"; exit 1

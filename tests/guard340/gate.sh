#!/bin/bash
# Гейт правки Роба 340 (Мак, ~2 мин): «по краям экрана иногда обламывается тень от деревьев на траве — будто учитывается старый
# узкий экран». Отсечение кусков по 16:9 верное; причина — защитная полоса GE: пешком у стены/дерева/машины ближняя плоскость кадра
# опускается до 0,25–0,3 м (homer.c camNear, main.c frameNear), полоса у near сужается до ±2,3 м, и треугольник земли или тени
# дерева (экспорт режет землю до 7 м), уходящий краем за камеру, GE выбрасывает целиком. Правило (viewer/ge_guard.h, main.c
# drawGeoG): в таких кадрах кусок/клетка у камеры рисуется по треугольникам, треугольник под риском — срезом по пирамиде полосы.
# Прежнее — flag ggold 1 (или сборка -DGG_OLD=1).
#   tests/guard340/gate.sh [EBOOT] [EBOOT_ДО_ПРАВКИ]   (по умолчанию viewer/build/EBOOT.PBP; LEVEL=путь к level.shr)
# 1) безголовый эмулятор (программная отрисовка выбрасывает треугольник за полосой, как железо): tests/guard340/mac_foot.txt —
#    Гомер пешком у теней деревьев, у каждой позы снимки прежнего (ggold 1) и нового подряд; tests/guard340/emu340.py — новое рисует
#    то, что модель GE называет выброшенным (≥ 20 % маски), и больше ничего не меняет; с EBOOT_ДО_ПРАВКИ — обязан упасть (КРАСНЫЙ);
# 2) модель GE (tests/guard340/ge340.py) на НАСТОЯЩЕМ коде среза (tests/guard340/guard_host.c, cc на Маке): позы у всех скоплений
#    теней уровня (ближняя 1,5/0,5/0,28/0,25 м) и позы CAMF прогона 1 — новое 0 px потерь, 0 промахов бокса, веер = идеальному;
#    прежнее (-DGG_OLD) теряет тени (КРАСНЫЙ пойман).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=python3
SCEN="$HOME/.claude/skills/shar-level-polish/scripts/scen.py"
EB="$(cd "$(dirname "${1:-viewer/build/EBOOT.PBP}")" && pwd)/$(basename "${1:-viewer/build/EBOOT.PBP}")"
[ -f "$EB" ] || { echo "нет EBOOT $EB"; exit 1; }
LEVEL=${LEVEL:-build/level.shr}; OUT=build/gates/guard340; mkdir -p "$OUT"; RUNS=${TWINS_ROOT:-$ROOT}/build/twins/scen/full
echo "EBOOT $(shasum -a 256 "$EB" | cut -c1-8); level.shr $(shasum -a 256 "$LEVEL" | cut -c1-8)"
cc -O2 -Wall -Iviewer -o "$OUT/guard_host" tests/guard340/guard_host.c -lm && \
cc -O2 -Wall -DGG_OLD -Iviewer -o "$OUT/guard_host_old" tests/guard340/guard_host.c -lm || { echo "FAIL: сборка guard_host"; exit 1; }
run() {   # имя EBOOT — безголовый эмулятор, свой HOME, по одному (программная отрисовка ест ядра)
  mkdir -p "$ROOT/$OUT/home_$1"; rm -rf "$RUNS/340-$1"
  SCEN_EBOOT="$2" SCEN_HOME="$ROOT/$OUT/home_$1" nice -n 10 python3 "$SCEN" "340-$1" tests/guard340/mac_foot.txt > "$OUT/scen_$1.log" 2>&1
}
run foot "$EB"
$PY tests/guard340/emu340.py "$RUNS/340-foot" --level "$LEVEL" --sheet "$OUT/foot_sheet.png" > "$OUT/emu.txt" 2>&1; e=$?
r=-1
if [ $# -ge 2 ] && [ -f "$2" ]; then
  run footold "$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
  $PY tests/guard340/emu340.py "$RUNS/340-footold" --level "$LEVEL" --poses "$RUNS/340-foot/smoke.txt" > "$OUT/emu_old.txt" 2>&1; r=$?   # позы — из прогона нового (near в CAMF)
fi
$PY tests/guard340/ge340.py --level "$LEVEL" --host "$OUT/guard_host" --host-old "$OUT/guard_host_old" --camf "$RUNS/340-foot/smoke.txt" > "$OUT/model.txt" 2>&1; m=$?
echo "эмулятор (прежнее и новое подряд у каждой позы):"; sed 's/^/  /' "$OUT/emu.txt" | grep -v '^  лист'
grep -h GGSTAT "$RUNS/340-foot/smoke.txt" | sed 's/^/  /'
[ $r -ge 0 ] && echo "движок до правки (красный): $(tail -1 "$OUT/emu_old.txt")"
echo "модель GE:"; grep -E "^  (прежнее|новое)|^    при ближней|^ИТОГ" "$OUT/model.txt" | sed 's/^/  /' | cut -c1-230
ok=1
[ $e -eq 0 ] || { echo "FAIL: эмулятор — $(tail -1 "$OUT/emu.txt")"; ok=0; }
[ $r -ne 0 ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: движок до правки прошёл проверку эмулятора"; ok=0; }
[ $m -eq 0 ] || { echo "FAIL: модель — $(tail -1 "$OUT/model.txt")"; ok=0; }
echo "подробно: $OUT/emu.txt, $OUT/model.txt; лист (прежнее | новое | отличия): $OUT/foot_sheet.png; кадры: $RUNS/340-foot"
if [ $ok -eq 1 ]; then echo "ИТОГ: PASS (у камеры с низкой ближней плоскостью GE больше не выбрасывает треугольники земли и теней; прежнее теряет — красный пойман)"; exit 0; fi
echo "ИТОГ: FAIL"; exit 1

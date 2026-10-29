#!/bin/bash
# Гейты кадра финала интерфейса, 16.10.2026 (Sonnet-Типографика): №623 (значок дома, блок таймера правее него), №630 (слово отсчёта по центру зелёным),
# №638 (появление бабла единым масштабом), №640 (ровные поля бабла), №646 (рамка растёт до 4–5 строк), hudBlk (блок без доезда после паузы).
# Каждый гейт: новый код ЗЕЛЁНЫЙ, прежнее поведение (-D<ИМЯ>_OLD=1, вторая сборка движка) КРАСНОЕ. Эмулятор только безголовый (scen.py, свой HOME на сборку).
#   tests/ui/final1016_gate.sh            все гейты;    FINAL_REUSE=1 — не пересобирать EBOOT, если уже есть
# Нужно: pspdev рядом с деревом, .venv, данные главного дерева (scen.py берёт build/ из shar-psp). Итог — строка на гейт «новый / старый».
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
OUT="${FINAL_OUT:-$ROOT/build/final1016}"; mkdir -p "$OUT"; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py; PY=python3
CHK="$PY tests/ui/final1016_check.py"; TAG="${FINAL_TAG:-$$}"
VARS="new HUD_HOME_ICON_OLD HUD_SHIFT_COND_OLD COUNTDOWN_LINE_OLD BUBBLE_UNIFORM_OLD BUBBLE_EVEN_OLD"
for v in $VARS; do
  [ "${FINAL_REUSE:-0}" = 1 ] && [ -f "$OUT/gb/$v/EBOOT.PBP" ] && continue
  ( mkdir -p "$OUT/gb/$v" && cd "$OUT/gb/$v" && OPT=""; [ "$v" != new ] && OPT="-DSHAR_OPT=-D$v=1"
    psp-cmake -S "$ROOT/viewer" -B . $OPT >/dev/null 2>&1 && cmake --build . -j4 >/dev/null 2>&1 ) &
done; wait
for v in $VARS; do [ -f "$OUT/gb/$v/EBOOT.PBP" ] || { echo "FAIL: нет сборки $v"; exit 2; }; done
run() {   # run ВАРИАНТ СЦЕНАРИЙ КЛЮЧ -> путь папки в $OUT/dir_КЛЮЧ_ВАРИАНТ
  SCEN_HOME="$OUT/gb/home_$1" SCEN_EBOOT="$OUT/gb/$1/EBOOT.PBP" timeout 1200 $PY "$SCEN" "g1016${TAG}_$3_$1" "tests/ui/final1016_$2_scenario.txt" 2>&1 | sed -n 's/^dir \([^ ]*\) .*/\1/p' > "$OUT/dir_$3_$1"
}
for v in new BUBBLE_UNIFORM_OLD; do run $v pop pop & done
for v in new BUBBLE_EVEN_OLD; do run $v bubble bubble & done
for v in new HUD_HOME_ICON_OLD HUD_SHIFT_COND_OLD COUNTDOWN_LINE_OLD; do run $v race race & done; wait
D() { cat "$OUT/dir_$1_$2" 2>/dev/null; }
rc=0
gate() {   # gate ИМЯ КОМАНДА НОВЫЙ СТАРЫЙ...
  local name="$1" kind="$2" new="$3"; shift 3; local n o line
  n=$($CHK $kind "$new" 2>&1); local nrc=$?
  line="$name: новый $( [ $nrc = 0 ] && echo ЗЕЛЁНЫЙ || echo "КРАСНЫЙ (плохо): ${n##*$'\n'}" )"
  for old in "$@"; do
    o=$($CHK $kind "$(D $kind $old)" 2>&1); local orc=$?
    line="$line; $old $( [ $orc != 0 ] && echo "красный (как нужно)" || echo "ЗЕЛЁНЫЙ (красный не пойман)" )"; [ $orc = 0 ] && rc=1
  done
  [ $nrc = 0 ] || rc=1; echo "$line"
}
gate "№638 появление бабла"          pop    "$(D pop new)"    BUBBLE_UNIFORM_OLD
gate "№640/№646 поля и рост рамки"   bubble "$(D bubble new)" BUBBLE_EVEN_OLD
gate "№623 значок дома, блок правее" race   "$(D race new)"   HUD_HOME_ICON_OLD HUD_SHIFT_COND_OLD
gate "№630 слово отсчёта по центру"  race   "$(D race new)"   COUNTDOWN_LINE_OLD
# hudBlk (Мак, функция из ui.c как есть)
hn=$($PY tests/ui/final1016_hudblk.py 2>&1); hnr=$?; ho=$($PY tests/ui/final1016_hudblk.py --old 2>&1); hor=$?
echo "hudBlk без доезда после паузы: новый $( [ $hnr = 0 ] && echo ЗЕЛЁНЫЙ || echo КРАСНЫЙ ); HUD_BLK_RESET_OLD $( [ $hor != 0 ] && echo 'красный (как нужно)' || echo 'ЗЕЛЁНЫЙ (красный не пойман)' )"
[ $hnr = 0 ] && [ $hor != 0 ] || rc=1
# №638 кривая (Мак): tests/ui/bubble_anim.c, красный -DBUBBLE_UNIFORM_OLD=1 использует старую таблицу PS2 и сам является прежним поведением
mkdir -p "$OUT/host"; cc -std=c11 -O2 -I viewer tests/ui/bubble_anim.c -lm -o "$OUT/host/ba" 2>/dev/null && "$OUT/host/ba" >/dev/null && echo "№638 кривая (host bubble_anim.c): зелёный" || { echo "№638 кривая: КРАСНЫЙ"; rc=1; }
[ $rc = 0 ] && echo "ИТОГ: PASS (новое зелёное, старое красное)" || echo "ИТОГ: FAIL"
exit $rc

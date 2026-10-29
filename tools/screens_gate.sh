#!/bin/bash
# Гейт экранов вокруг игры в эмуляторе: заставка → лицензия → BootupLoad → ролики → СРАЗУ меню (правка Роба 33) →
# простой → титульный «Press START» → одно нажатие → меню (правка Роба 24) → загрузка уровня (газета влетает, почти во
# весь экран, показ не короче минимума — правка Роба 35) → игра → QUIT GAME → загрузка меню (LoadingFE.scr) → меню.
#   tools/screens_gate.sh [--red [OLD_EBOOT]] [DIR]   DIR = где лежат EBOOT.PBP и данные с boot.shr / load.shr (по умолчанию build/)
#   SCREENS_SHOTS=папка           куда положить снимки и макеты (по умолчанию DIR/ui_shots)
# Запускает tools/smoke.sh со сценарием tools/screens_scenario.txt (общая очередь PPSSPP), потом tools/screens_check.py.
# --red: сначала КРАСНЫЕ прогоны на подброшенном плохом входе, потом зелёный:
#   (а) сценарий + «flag titledeaf / loadfast / spinlag» (первое нажатие на титульном теряется, загрузка без минимума,
#       разворот газеты рывками) — проверка обязана поймать title_press, load_min, spin_smooth;
#   (б) прежняя раскладка газеты (--news-red) — поймать news_size;
#   (в) OLD_EBOOT (прежний движок с титульным на старте; по умолчанию не запускается) — поймать title_boot.
# Код выхода 0 = OK; первая строка вывода — итог.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RED=0; OLD=""
if [ "${1:-}" = --red ]; then RED=1; shift; case "${1:-}" in *.PBP) OLD="$1"; shift ;; esac; fi
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
. "$ROOT/.venv/bin/activate"
run() {   # $1 = сценарий, $2 = папка данных -> печатает папку итога
  local log out; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$2" 2>&1)
  out="$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
  [ -f "$out/smoke.txt" ] || { echo "screens_gate: смоук не отработал: $(echo "$log" | head -3)" >&2; return 1; }
  echo "$out"
}
BAD=0
red() { local r rc; r=$(python "$ROOT/tools/screens_check.py" "$1" --data "$SRC" "${@:2}"); rc=$?; echo "$r" | head -5; [ $rc = 0 ] || BAD=1; }
if [ $RED = 1 ]; then
  TMP="$ROOT/build/screens_gate/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$TMP"
  sed 's/^flag idle 2$/flag idle 2\nflag titledeaf\nflag loadfast\nflag spinlag/' "$ROOT/tools/screens_scenario.txt" > "$TMP/planted.txt"
  echo "(а) подброшено: titledeaf, loadfast, spinlag"
  OUT=$(run "$TMP/planted.txt" "$SRC") || exit 1
  red "$OUT" --expect-fail title_press,load_min,spin_smooth
  if [ -n "$OLD" ]; then
    echo "(в) прежний движок $OLD: титульный на старте"
    mkdir -p "$TMP/old"; for f in "$SRC"/*; do [ "$(basename "$f")" = EBOOT.PBP ] || ln -s "$f" "$TMP/old/"; done
    cp "$OLD" "$TMP/old/EBOOT.PBP"
    OUTO=$(run "$ROOT/tools/screens_scenario.txt" "$TMP/old") || exit 1
    red "$OUTO" --expect-fail title_boot
  fi
fi
OUT=$(run "$ROOT/tools/screens_scenario.txt" "$SRC") || exit 1
if [ $RED = 1 ]; then
  echo "(б) прежняя раскладка газеты"
  red "$OUT" --news-red --expect-fail news_size
fi
python "$ROOT/tools/screens_check.py" "$OUT" --data "$SRC" --copy "${SCREENS_SHOTS:-$SRC/ui_shots}"; RC=$?
echo "прогон: ${OUT#$ROOT/} (smoke.txt, снимки)"
[ $BAD = 0 ] || { echo "screens_gate: отрицательный прогон НЕ красный — проверка слепая"; exit 1; }
exit $RC

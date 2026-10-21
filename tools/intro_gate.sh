#!/bin/bash
# Гейт интро в эмуляторе: заставка -> vuglogo -> foxlogo -> gracie -> radlogo -> intro -> главное меню.
#   tools/intro_gate.sh [--red [OLD_MOVIES_DIR]] [DIR]   DIR = где лежат EBOOT.PBP и данные с movies/ (по умолчанию build/)
#   --red: сначала красные прогоны (правка Роба 49): «flag tvframe» — рамка правки 32 поверх полей -> sides; прежние ролики
#          OLD_MOVIES_DIR (правка 32: окно рамки, картинка шире 4:3; путь .../movies) -> layout; потом зелёный
#   INTRO_SHOTS=папка           куда положить снимки и эталоны ffmpeg (по умолчанию DIR/ui_shots)
# Запускает tools/smoke.sh со сценарием tools/intro_scenario.txt (общая очередь PPSSPP), потом tools/intro_check.py:
# кадры роликов = ffmpeg на Маке, radlogo доигран целиком со звуком, START пропускает, куча до и после одна ±64 КБ.
# Код выхода 0 = OK; первая строка вывода — итог.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RED=0; OLDMOV=""
if [ "${1:-}" = --red ]; then RED=1; shift; case "${1:-}" in */movies|*/movies/) OLDMOV="$1"; shift ;; esac; fi
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
. "$ROOT/.venv/bin/activate"
run() {   # $1 = сценарий -> папка итога
  local log out; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
  out="$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
  [ -f "$out/smoke.txt" ] || { echo "intro_gate: смоук не отработал: $(echo "$log" | head -3)" >&2; return 1; }
  echo "$out"
}
BAD=0
red() { local r rc; r=$(python "$ROOT/tools/intro_check.py" "$@"); rc=$?; echo "$r" | head -4; [ $rc = 0 ] || BAD=1; }
if [ $RED = 1 ]; then   # правка Роба 49: рамка поверх полей и прежние ролики в окне рамки — обязаны провалиться
  TMP="$ROOT/build/intro_gate/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$TMP"
  sed 's/^flag intro$/flag intro\nflag tvframe/' "$ROOT/tools/intro_scenario.txt" > "$TMP/planted.txt"
  echo "(а) подброшено: flag tvframe (рамка правки 32 поверх полей)"
  OUTR=$(run "$TMP/planted.txt") || exit 1
  red "$OUTR" --expect-fail sides
  if [ -n "$OLDMOV" ]; then
    echo "(б) прежние ролики $OLDMOV (правка 32: окно рамки, шире 4:3)"
    mkdir -p "$TMP/old"; ln -s "$OLDMOV" "$TMP/old/movies"
    red "$OUTR" --data "$TMP/old" --expect-fail layout
  fi
fi
OUT=$(run "$ROOT/tools/intro_scenario.txt") || exit 1
python "$ROOT/tools/intro_check.py" "$OUT" --data "$SRC" --copy "${INTRO_SHOTS:-$SRC/ui_shots}"; RC=$?
echo "прогон: ${OUT#$ROOT/} (smoke.txt, снимки)"
[ $BAD = 0 ] || { echo "intro_gate: отрицательный прогон НЕ красный — проверка слепая"; exit 1; }
exit $RC

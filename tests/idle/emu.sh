#!/bin/bash
# Простой меню как в оригинале (правка Роба 33): меню -> титульный -> ролик простоя movies\demo.rmv «- DEMO -» -> кнопка -> меню.
# Сценарий tests/idle/scenario.txt через tools/smoke.sh (общая очередь tools/ppsspp_run.sh), разбор tests/idle/check.py.
#   tests/idle/emu.sh [DIR]              зелёный прогон
#   tests/idle/emu.sh --red [DIR]        сначала КРАСНЫЙ прогон на подброшенном плохом входе («flag demodeaf» — ролик не
#                                        слышит кнопок, возврата в меню нет; «flag demonolabel» — без надписи): обязан
#                                        провалить demo_return и demo_label; потом зелёный
#   IDLE_SHOTS=папка                     куда положить снимок и макет (по умолчанию DIR/ui_shots)
# DIR — EBOOT.PBP и данные с boot.shr и movies/demo.smv (по умолчанию build/). Код 0 = OK; первая строка — итог.
set -u; cd "$(dirname "$0")/../.."
RED=0; [ "${1:-}" = --red ] && { RED=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d)
run() {   # $1 сценарий -> папка прогона
  SMOKE_SCN="$1" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
  REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
  [ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")" >&2; return 2; }
  echo "$REP"
}
if [ $RED = 1 ]; then
  sed 's/^flag demoidle 2$/flag demoidle 2\nflag demodeaf\nflag demonolabel/' tests/idle/scenario.txt > "$LOG/planted.txt"
  echo "(красный) подброшено: flag demodeaf, flag demonolabel"
  R=$(run "$LOG/planted.txt") || exit 1; echo "прогон: $R"
  $PY tests/idle/check.py "$R" --expect-fail demo_return,demo_label || { echo "idle: отрицательный прогон НЕ красный — проверка слепая"; exit 1; }
fi
R=$(run tests/idle/scenario.txt) || exit 1
$PY tests/idle/check.py "$R" --copy "${IDLE_SHOTS:-$SRC/ui_shots}"; rc=$?
echo "прогон: $R"; exit $rc

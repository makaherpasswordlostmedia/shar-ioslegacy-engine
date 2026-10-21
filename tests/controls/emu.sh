#!/bin/bash
# Раскладка пешком как в оригинале (frontend.p3d ControllerPS2.pag: X JUMP, □ ATTACK, ○ DASH / SPRINT) в эмуляторе:
# сценарий tests/controls/scenario.txt через tools/smoke.sh (общая очередь tools/ppsspp_run.sh), разбор tests/controls/check.py.
#   tests/controls/emu.sh [DIR]              зелёный: ↑ — шаг 4 м/с, ↑+○ — бег 8 м/с, □ — пинок, X □ — удар в прыжке, X X □ — стомп
#   tests/controls/emu.sh --negative [DIR]   красный контроль (обязан упасть): «flag oldfootpad» — прежняя раскладка порта
#                                            (стик сразу бег, ○ — стомп в воздухе, бега по ○ нет)
# DIR — EBOOT.PBP и данные (по умолчанию build/). Раскладка в машине — tests/svc/emu.sh (○ тормоз, □ ручник, SELECT RESET CAR).
set -u; cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d)
run() {   # $1 сценарий -> код check.py
  SMOKE_SCN="$1" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
  REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
  [ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; return 2; }
  echo "прогон: $REP"; $PY tests/controls/check.py "$REP"
}
if [ $NEG = 0 ]; then run tests/controls/scenario.txt; exit $?; fi
sed 's/^flag player$/flag player\nflag oldfootpad/' tests/controls/scenario.txt > "$LOG/neg_oldpad.txt"
run "$LOG/neg_oldpad.txt"; rc=$?
[ $rc = 1 ] && { echo "PASS (красный контроль «прежняя раскладка» пойман)"; exit 0; }
echo "FAIL (красный контроль «прежняя раскладка» НЕ пойман, код $rc)"; exit 1

#!/bin/bash
# Переходы как в оригинале и выброс при взрыве — в эмуляторе: сценарий tests/transit/scenario.txt через tools/smoke.sh
# (общая очередь tools/ppsspp_run.sh), разбор tests/transit/check.py.
#   tests/transit/emu.sh [DIR]              зелёный: взрыв выбрасывает Гомера наружу (EJECT), ирис оригинала на всех
#                                           переходах сценария (test, overtop, seat, room_in, room_out, msn), снимки
#   tests/transit/emu.sh --negative [DIR]   красный контроль: тот же сценарий с flag noeject + flag noiris в начале —
#                                           проверка обязана упасть (Гомер в остове, ириса нет)
# DIR — EBOOT.PBP и данные (по умолчанию build/). FPS коротких сцен сценария не в счёт (у смоука свой гейт).
set -u; cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d); SCN=tests/transit/scenario.txt
if [ $NEG = 1 ]; then SCN="$LOG/scenario_neg.txt"; { echo "flag noeject"; echo "flag noiris"; cat tests/transit/scenario.txt; } > "$SCN"; fi
SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
[ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; exit 1; }
echo "прогон: $REP"
$PY tests/transit/check.py "$REP"; RC=$?
if [ $NEG = 1 ]; then
  [ $RC != 0 ] && { echo "PASS (красный контроль пойман: без выброса и ириса проверка упала)"; exit 0; }
  echo "FAIL (красный контроль НЕ пойман)"; exit 1
fi
exit $RC

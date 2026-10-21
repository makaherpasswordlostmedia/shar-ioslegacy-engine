#!/bin/bash
# Правки Роба 42 и 44 в эмуляторе: сценарий tests/svc/scenario.txt через tools/smoke.sh (общая очередь
# tools/ppsspp_run.sh), разбор tests/svc/check.py.
#   tests/svc/emu.sh [DIR]              зелёный: режим игрока — L+R+△ обычный △, R+SELECT без счётчика, SELECT в машине —
#                                       RESET CAR, ○ — тормоз/назад
#   tests/svc/emu.sh --negative [DIR]   красные контроли (оба обязаны упасть): 1) тот же сценарий в служебном режиме
#                                       (flag service) — служебные полёт и счётчик доступны, RESET по SELECT нет;
#                                       2) вместо ○ нажимается ↑ (кнопка без тормоза, как ○ до правки 42)
# DIR — EBOOT.PBP и данные (по умолчанию build/). FPS коротких сцен не в счёт (у смоука свой гейт).
set -u; cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d)
run() {   # $1 сценарий -> код check.py
  SMOKE_SCN="$1" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
  REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
  [ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; return 2; }
  echo "прогон: $REP"; $PY tests/svc/check.py "$REP"
}
if [ $NEG = 0 ]; then run tests/svc/scenario.txt; exit $?; fi
sed 's/^flag player$/flag service/' tests/svc/scenario.txt > "$LOG/neg_service.txt"
sed 's/^press circle /press up /' tests/svc/scenario.txt > "$LOG/neg_circle.txt"
ok=1
run "$LOG/neg_service.txt"; [ $? = 1 ] || { echo "FAIL (красный контроль «служебный режим» НЕ пойман)"; ok=0; }
run "$LOG/neg_circle.txt"; [ $? = 1 ] || { echo "FAIL (красный контроль «○ без тормоза» НЕ пойман)"; ok=0; }
[ $ok = 1 ] && { echo "PASS (оба красных контроля пойманы)"; exit 0; }
exit 1

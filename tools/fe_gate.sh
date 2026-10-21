#!/bin/bash
# Гейт гостиной главного меню (пункт 12а) в эмуляторе: снимки меню на трёх пунктах, частота кадров меню, память.
#   tools/fe_gate.sh [--red] [DIR]   DIR = где лежат EBOOT.PBP и данные (по умолчанию build/), fe.shr — оттуда же
#   --red: сначала красный прогон (правка Роба 49): «flag flynoframe» — в перелёте камеры меню без рамки-телевизора -> fly_frame
#   FE_SHOTS=папка            куда положить снимки (по умолчанию DIR/ui_shots)
# Запускает tools/smoke.sh со сценарием tools/fe_scenario.txt (общая очередь PPSSPP), потом tools/fe_check.py.
# Код выхода 0 = OK; первая строка вывода — итог.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RED=0; if [ "${1:-}" = --red ]; then RED=1; shift; fi
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
. "$ROOT/.venv/bin/activate"
if [ $RED = 1 ]; then
  TMP="$ROOT/build/fe_gate/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$TMP"
  sed 's/^flag menu$/flag menu\nflag flynoframe/' "$ROOT/tools/fe_scenario.txt" > "$TMP/planted.txt"
  LOG=$(SMOKE_SCN="$TMP/planted.txt" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
  OUTR="$ROOT/$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
  [ -f "$OUTR/smoke.txt" ] || { echo "fe_gate: красный смоук не отработал"; exit 1; }
  python "$ROOT/tools/fe_check.py" "$OUTR" "$SRC/fe.shr" --expect-fail fly_frame || { echo "fe_gate: отрицательный прогон НЕ красный — проверка слепая"; exit 1; }
fi
LOG=$(SMOKE_SCN="$ROOT/tools/fe_scenario.txt" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
OUT="$ROOT/$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
[ -f "$OUT/smoke.txt" ] || { echo "fe_gate: смоук не отработал"; echo "$LOG" | head -5; exit 1; }
python "$ROOT/tools/fe_check.py" "$OUT" "$SRC/fe.shr" --copy "${FE_SHOTS:-$SRC/ui_shots}"; RC=$?
echo "прогон: ${OUT#$ROOT/} (smoke.txt, снимки); смоук-отчёт: $(echo "$LOG" | head -1)"
exit $RC

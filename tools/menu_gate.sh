#!/bin/bash
# Гейт пункта 12а в эмуляторе: заставка → главное меню → NEW GAME → загрузка → игра → пауза → QUIT GAME → меню, 5 кругов.
#   tools/menu_gate.sh [--red] [DIR]   DIR = где лежат EBOOT.PBP и данные (по умолчанию build/); --red — сначала красный
#                               прогон: звуки меню заглушены (flag uisfx0) -> menu_sfx
#   MENU_SHOTS=папка            куда положить снимки фаз (по умолчанию DIR/ui_shots)
# Запускает tools/smoke.sh со сценарием tools/menu_scenario.txt (общая очередь PPSSPP), потом tools/menu_check.py:
# куча при входе в меню после 5 кругов = первой ±64 КБ, курсор не встаёт на затемнённые пункты, запуск только NEW GAME.
# Код выхода 0 = OK; первая строка вывода — итог.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RED=0; if [ "${1:-}" = --red ]; then RED=1; shift; fi
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
. "$ROOT/.venv/bin/activate"
if [ $RED = 1 ]; then   # 29.09: звуки меню заглушены («flag uisfx0») -> menu_sfx; стингеры — только если их дорожек нет в music.sap
  TMP="$ROOT/build/menu_gate/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$TMP"
  sed 's/^flag menu$/flag menu\nflag uisfx0/' "$ROOT/tools/menu_scenario.txt" > "$TMP/planted.txt"
  LOG=$(SMOKE_SCN="$TMP/planted.txt" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
  OUTR="$ROOT/$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
  [ -f "$OUTR/smoke.txt" ] || { echo "menu_gate: красный смоук не отработал"; exit 1; }
  python "$ROOT/tools/menu_check.py" "$OUTR" --expect-fail menu_sfx || { echo "menu_gate: отрицательный прогон НЕ красный — проверка слепая"; exit 1; }
fi
LOG=$(SMOKE_SCN="$ROOT/tools/menu_scenario.txt" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
OUT="$ROOT/$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
[ -f "$OUT/smoke.txt" ] || { echo "menu_gate: смоук не отработал"; echo "$LOG" | head -5; exit 1; }
python "$ROOT/tools/menu_check.py" "$OUT" --copy "${MENU_SHOTS:-$SRC/ui_shots}"; RC=$?
echo "прогон: ${OUT#$ROOT/} (smoke.txt, menu_check.txt, снимки); смоук-отчёт: $(echo "$LOG" | head -1)"
exit $RC

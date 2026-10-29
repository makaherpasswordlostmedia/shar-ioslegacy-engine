#!/bin/bash
# Гейт правки Роба 206 (подписи рядом с △ — что делает действие): у Мардж на старте «Talk To Marge», у своей машины пешком
# «Get Into Car» (строки ACTTEXT журнала) и пункт ActionText в ui.shr. КРАСНЫЙ: ui.shr без пункта (UI_ACTION_LABEL_OFF=1) — подписи
# на экране нет: снимок рядом со значком без белых букв. Эмулятор безоконный, без звука (tools/twins)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; PY="$ROOT/.venv/bin/python"; OUT=build/action_label; mkdir -p "$OUT"
UI_ACTION_LABEL_OFF=1 "$PY" tools/ui_export.py --out "$OUT/ui_off.shr" > "$OUT/ui_off.txt" 2>&1 || { echo "FAIL: экспорт без подписи"; exit 2; }
"$PY" tools/ui_export.py --out "$OUT/ui_on.shr" > "$OUT/ui_on.txt" 2>&1 || { echo "FAIL: экспорт"; exit 2; }
"$PY" tests/ui/action_label.py red "$OUT/ui_off.shr" > "$OUT/red.txt" 2>&1; rr=$?; tail -1 "$OUT/red.txt"
"$PY" tests/ui/action_label.py green "$OUT/ui_on.shr" > "$OUT/green.txt" 2>&1; rg=$?; tail -1 "$OUT/green.txt"
[ $rr -ne 0 ] && [ $rg -eq 0 ] && echo "PASS: красный пойман, зелёный — подписи у △" || { echo "FAIL"; exit 1; }

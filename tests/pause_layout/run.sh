#!/bin/bash
# Гейт правок Роба 150/151 (пауза: «больше воздуха между строк, рамку меньше, всё усредни»; аудит интерфейса): хост, без эмулятора.
# Сначала КРАСНЫЙ: прежняя раскладка (PAUSE_OLD=1 — сжатые строки шагом 22, рамка 240x226 с запасом, OPTIONS без заголовка, мелкие подписи SOUND,
# подсказка Back на доске, поля разные) обязана упасть; потом ЗЕЛЁНЫЙ: tests/pause_layout/check.py на текущей раскладке.
#   tests/pause_layout/run.sh [SHOTS_DIR]   SHOTS_DIR — снимки x2 обеих раскладок (old/, new/); код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; SH="${1:-}"
A=(); B=()
[ -n "$SH" ] && { mkdir -p "$SH/old" "$SH/new"; A=(--shots "$SH/old"); B=(--shots "$SH/new"); }
RED=$(PAUSE_OLD=1 "$PY" tests/pause_layout/check.py "${A[@]+"${A[@]}"}" 2>&1)
if [ $? -eq 0 ]; then echo "FAIL: прежняя сжатая раскладка прошла — гейт слепой"; echo "$RED"; exit 1; fi
echo "красный как надо: $(echo "$RED" | grep -c '^      - ') нарушений на прежней раскладке"
DENSE=$(UI_DENSE=1 "$PY" tests/pause_layout/check.py 2>&1); rc=$?
if [ "$rc" = 0 ] || ! printf '%s\n' "$DENSE" | grep -q '163 ширина\|163 заголовок'; then
  echo "FAIL: 163 UI_DENSE не пойман новым договором"; exit 1
fi
echo "красный163: прежняя ширина/заголовок пойманы"
"$PY" tests/pause_layout/check.py "${B[@]+"${B[@]}"}"

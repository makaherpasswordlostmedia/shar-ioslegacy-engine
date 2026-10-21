#!/bin/bash
# Гейт правки Роба 129 (текстуры уровня: T4 без потерь для 16 цветов, вывески 128 px), только файлы, на Маке: tools/tex_gate.py.
# Сначала КРАСНЫЕ (обязаны упасть): полубайты наоборот (--swap-nibbles), строка T4 как у T8 (--t8-rows), прежний уровень
# (OLD — сборка до правки 129: секция 4.20 МБ, вывески 256, без texsrc). Потом ЗЕЛЁНЫЙ на LEVEL.
#   tests/tex129/run.sh [LEVEL] [OLD]   по умолчанию build/level.shr; OLD — необязателен; код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
LV="${1:-$ROOT/build/level.shr}"; OLD="${2:-}"; PY="$ROOT/.venv/bin/python"
T="$ROOT/build/gates/tex129/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T"
red() {   # $1 — имя, остальное — аргументы tex_gate
  local n=$1; shift
  if "$PY" tools/tex_gate.py "$@" > "$T/$n.txt" 2>&1; then echo "FAIL: подброска $n прошла — проверка слепая"; exit 1; fi
  echo "красный как надо ($n): $(grep -m1 КРАСНОЕ "$T/$n.txt" | cut -c1-160)"
}
red swap "$LV" --swap-nibbles
red t8rows "$LV" --t8-rows
[ -n "$OLD" ] && red old "$OLD"
if [ -n "$OLD" ]; then "$PY" tools/tex_gate.py "$LV" --old "$OLD"; else "$PY" tools/tex_gate.py "$LV"; fi

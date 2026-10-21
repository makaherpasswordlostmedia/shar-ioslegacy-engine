#!/bin/bash
# Гейт правки Роба 248 (пончик и статуя Lard Lad дальше 50 м): tests/lod/far_full.py. Сначала КРАСНЫЙ, потом ЗЕЛЁНЫЙ:
#   1. уровень до 570ac3a (дальние версии кусков города; эталон build/seams/ref/level_pre_seams.shr) — обязан упасть
#   2. выпуск build/level.shr — PASS
# Запуск: tests/lod/far_full.sh [NEW.shr] [OLD.shr]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
NEW=${1:-build/level.shr}; OLD=${2:-build/seams/ref/level_pre_seams.shr}; OUT=build/tmp_conv/lod_far_full; mkdir -p "$OUT"
[ -f "$NEW" ] && [ -f "$OLD" ] || { echo "FAIL: нет $NEW или $OLD"; exit 1; }
red=0; green=0
if $PY tests/lod/far_full.py "$OLD" > "$OUT/red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: $OLD — $(tail -1 "$OUT/red.txt")"
else echo "красный ($OLD): упал, как должен — $(grep -m1 '^FAIL 1' "$OUT/red.txt" | cut -c1-120)"; red=1; fi
if $PY tests/lod/far_full.py "$NEW" > "$OUT/green.txt" 2>&1; then echo "зелёный ($NEW): $(grep -m1 '^ok   1' "$OUT/green.txt" | cut -c1-120)"; green=1
else echo "ЗЕЛЁНЫЙ УПАЛ: $NEW — $(grep -m1 '^FAIL' "$OUT/green.txt")"; fi
[ $red = 1 ] && [ $green = 1 ] && { echo "far_full gate: PASS (красный пойман, зелёный)"; exit 0; }
echo "far_full gate: FAIL"; exit 1

#!/bin/bash
# Гейт правки 143(а): пакеты персонажей миссий несут только нужные клипы (tools/char_export.py --npc, tools/chr_check.py). Мак, CPU.
# Сначала КРАСНЫЙ — обязан упасть: (1) bart без одного жеста разговора (--drop-clip dialogue_thinking) — «нет клипа»;
# (2) bart старым полным экспортом (без --npc, 65 клипов) — «больше 200 КБ». Потом ЗЕЛЁНЫЙ на build/chars. Итог: build/chr/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/chr; mkdir -p "$OUT"; PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
BART="--name bart --model art/chars/bart_m.p3d --anims art/chars/bart_a.p3d"
plant() {   # $1 = имя подброски, дальше — флаги char_export для bart; остальные пакеты — копии build/chars
  local d="$OUT/red_$1"; rm -rf "$d"; mkdir -p "$d/chars"; cp build/chars/*.chr "$d/chars/"; shift
  $PY tools/char_export.py $BART "$@" --out "$d/chars/bart.chr" > "$d/export.txt" 2>&1 || { echo "FAIL: экспорт подброски"; exit 1; }
  $PY tools/chr_check.py --root "$d" > "$d/check.txt" 2>&1
}
red=0
plant drop --npc --drop-clip dialogue_thinking; rc=$?
if [ $rc -ne 0 ] && grep -q "bart.chr: нет клипов \['dialogue_thinking'\]" "$OUT/red_drop/check.txt"; then echo "красный (без жеста): упал, как должен"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: пакет без dialogue_thinking прошёл"; fi
plant full; rc=$?
if [ $rc -ne 0 ] && grep -q "bart.chr: .* > 204800" "$OUT/red_full/check.txt"; then echo "красный (полный пакет): упал, как должен — $(grep -m1 'bart.chr:' "$OUT/red_full/check.txt")"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: полный bart.chr прошёл"; fi
$PY tools/chr_check.py > "$OUT/green.txt" 2>&1; rc=$?
grep "FAIL\|RESULT" "$OUT/green.txt"
if [ $red -eq 2 ] && [ $rc -eq 0 ]; then echo "PASS: красный 2/2 пойман, зелёный $(grep -m1 RESULT "$OUT/green.txt" | cut -d' ' -f2-)"; exit 0; fi
echo "FAIL: красный $red/2, зелёный rc=$rc"; exit 1

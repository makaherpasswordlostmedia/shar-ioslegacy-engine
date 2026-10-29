#!/bin/bash
# Гейт правки Роба 134 (музыка при наезде на газету): tools/fe_music_check.py — переходы музыки от темы меню до экрана
# загрузки только из fade_transitions l1_music.rms, один стингер, без обрыва, затухание и доля из данных.
# КРАСНЫЙ: журнал прежнего поведения (Loading_screen на × + Newspaper_Spin: FE_trans01 -> FE_trans02) обязан упасть —
#   FE_MUSIC_RED="<smoke.txt> ..." (по умолчанию смоук основной копии 30.09; смоук с «flag femusold» — тоже прежнее).
# ЗЕЛЁНЫЙ: FE_MUSIC_LOG=<smoke.txt> нового смоука меню (tools/smoke.sh, сценарий tests/fe_music/scenario.txt).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/fe_music; mkdir -p "$OUT"
RED="${FE_MUSIC_RED:-$HOME/Downloads/shar-psp/build/smoke/20260930-120506/smoke.txt}"
GREEN="${FE_MUSIC_LOG:-}"
red=0; nred=0
for L in $RED; do
  nred=$((nred + 1))
  "$PY" tools/fe_music_check.py "$L" > "$OUT/red_$nred.txt" 2>&1; rc=$?
  if [ $rc -ne 0 ] && grep -q "не из fade_transitions\|стингера подряд" "$OUT/red_$nred.txt"; then echo "красный ($L): упал, как должен"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН: $L (rc=$rc)"; fi
done
[ -n "$GREEN" ] || { echo "FAIL: нет FE_MUSIC_LOG (журнал нового смоука)"; exit 1; }
"$PY" tools/fe_music_check.py "$GREEN" > "$OUT/green.txt" 2>&1; rc=$?
cat "$OUT/green.txt"
if [ $red -eq $nred ] && [ $nred -gt 0 ] && [ $rc -eq 0 ]; then echo "PASS: красный $red/$nred пойман, зелёный — тема меню -> один Newspaper_Spin по доле"; exit 0; fi
echo "FAIL: красный $red/$nred, зелёный rc=$rc"; exit 1

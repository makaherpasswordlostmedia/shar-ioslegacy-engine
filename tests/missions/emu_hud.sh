#!/bin/bash
# HUD миссий в EBOOT (отзыв Роба 28.09): таймер и счётчик кругов не рисуются друг на друге (стопка оверлеев, ui.c), текст
# задания/провала всегда влезает в рамку (перенос по рамке, ui.c fitW) — все тексты уровня 1. Эмулятор, tools/smoke.sh.
#   tests/missions/emu_hud.sh [DIR]              -> PASS/FAIL
#   tests/missions/emu_hud.sh --negative [DIR]   подложены наложение (uistack 0) и не влезающая строка (uifitplant):
#                                                сверка обязана упасть (тогда PASS)
cd "$(dirname "$0")/../.."
NEG=0; if [ "${1:-}" = --negative ]; then NEG=1; shift; fi
DIR="${1:-build}"; SCN=tests/missions/hud_scenario.txt
if [ $NEG = 1 ]; then
  mkdir -p build/emu; SCN=build/emu/hud_negative.txt
  awk '{ if ($0 == "flag uifit") print "flag uifitplant"; else print; if ($0 == "flag msn") print "flag uistack 0" }' tests/missions/hud_scenario.txt > "$SCN"
fi
OUT=$(SMOKE_SCN="$SCN" tools/smoke.sh "$DIR" 2>&1); RC=$?
REP=$(echo "$OUT" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)
if [ -z "$REP" ] || [ ! -f "$REP/smoke.txt" ]; then echo "$OUT" | tail -5; echo "FAIL: нет отчёта смоука"; exit 1; fi
.venv/bin/python tests/missions/hud_check.py "$REP/smoke.txt" "$RC"; R=$?
echo "отчёт: $REP"
if [ $NEG = 1 ]; then
  if [ $R != 0 ]; then echo "PASS (отрицательный контроль: сверка упала, как должна)"; exit 0; fi
  echo "FAIL (отрицательный контроль прошёл — сверка ничего не ловит)"; exit 1
fi
if [ $R = 0 ]; then echo PASS; else echo FAIL; exit 1; fi

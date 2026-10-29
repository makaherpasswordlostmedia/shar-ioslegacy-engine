#!/bin/bash
# Миссия m0 «The Cola Caper» в EBOOT (пункт 8): сценарий tests/missions/m0_scenario.txt в эмуляторе (tools/smoke.sh:
# FPS/кадры/память — как у смоука) + сверка хода миссии по строкам MSN из smoke.txt (tests/missions/m0_check.py):
# разговор с Мардж по △, диалог, посадка по △, езда к Kwik-E-Mart (сфера), вход в магазин. Без комнат (крючок
# mvSetInterior) миссия обязана стоять у двери — честный конец прохода; с комнатами сценарий идёт дальше (Апу, ведёрко).
#   tests/missions/emu_m0.sh [DIR]              DIR — EBOOT + данные (по умолчанию build/) -> PASS/FAIL
#   tests/missions/emu_m0.sh --negative [DIR]   отрицательный контроль: после посадки машина к цели встаёт только в 25 м (msnfar) —
#                                               этап «доехать» обязан НЕ засчитаться, сверка обязана упасть (тогда PASS)
#   tests/missions/emu_m0.sh --negative-voice [DIR]  отрицательный контроль озвучки: флаг uinovoice (голоса «нет») —
#                                               строки «VOICE none ... нет голоса», сверка обязана упасть (тогда PASS)
cd "$(dirname "$0")/../.."
NEG=0; if [ "${1:-}" = --negative ]; then NEG=1; shift; elif [ "${1:-}" = --negative-voice ]; then NEG=2; shift; fi
DIR="${1:-build}"; SCN=tests/missions/m0_scenario.txt
if [ $NEG = 1 ]; then
  mkdir -p build/emu; SCN=build/emu/m0_negative.txt
  awk '{ if ($0 == "flag msngo" && ++n >= 2) print "flag msnfar 25"; else print }' tests/missions/m0_scenario.txt > "$SCN"
fi
if [ $NEG = 2 ]; then
  mkdir -p build/emu; SCN=build/emu/m0_novoice.txt
  awk '{ print; if ($0 == "flag msn") print "flag uinovoice" }' tests/missions/m0_scenario.txt > "$SCN"
fi
OUT=$(SMOKE_SCN="$SCN" tools/smoke.sh "$DIR" 2>&1); RC=$?
REP=$(echo "$OUT" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)
if [ -z "$REP" ] || [ ! -f "$REP/smoke.txt" ]; then echo "$OUT" | tail -5; echo "FAIL: нет отчёта смоука"; exit 1; fi
.venv/bin/python tests/missions/m0_check.py "$REP/smoke.txt" "$RC"; R=$?
echo "отчёт: $REP"
if [ $NEG != 0 ]; then
  if [ $R != 0 ]; then echo "PASS (отрицательный контроль: сверка упала, как должна)"; exit 0; fi
  echo "FAIL (отрицательный контроль прошёл — сверка ничего не ловит)"; exit 1
fi
if [ $R = 0 ]; then echo PASS; else echo FAIL; exit 1; fi

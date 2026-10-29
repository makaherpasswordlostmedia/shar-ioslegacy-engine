#!/bin/bash
# Читаемость текстов миссий на экране PSP 480x272 (Роб 28.09): каждый текст миссии (рамка задания HUD, круги, «этап
# пройден», брифинг, провал) — своя грань шрифта Scrooby, мягкий шаг: заглавная H не меньше MISSION_CAP_MIN_PX и шрифт не
# крупнее MISSION_EFF_MAX от простого масштаба 272/480 (tools/ui_export.py), буквы не растянуты, надпись в своей рамке. Данные — пакет ui.shr, как его собирает tools/ui_export.py. Тексты из данных миссии (задания,
# причины/подсказки провала, названия/описания брифинга) на вписывание проверяет движок: tests/missions/emu_hud.sh (uifit).
# Красный: подложены мелкий шрифт описания (--plant-tiny) и раздутый причины провала (--plant-huge) — обе обязаны упасть.
cd "$(dirname "$0")/../.."
export UI_SCRATCH="${UI_SCRATCH:-$PWD/build/emu/ui}"
echo "== подложен мелкий шрифт (отрицательный контроль, обязан упасть):"
.venv/bin/python tools/ui_export.py legibility --plant-tiny | grep -E "^FAIL|тексты"; N1=${PIPESTATUS[0]}
echo "== подложен раздутый шрифт (отрицательный контроль, обязан упасть):"
.venv/bin/python tools/ui_export.py legibility --plant-huge | grep -E "^FAIL|тексты"; N2=${PIPESTATUS[0]}
echo "== как собрано:"
.venv/bin/python tools/ui_export.py legibility; POS=$?
if [ "$N1" != 0 ] && [ "$N2" != 0 ] && [ $POS = 0 ]; then echo PASS; else echo "FAIL (мелкий: код $N1, раздутый: код $N2, как собрано: код $POS)"; exit 1; fi

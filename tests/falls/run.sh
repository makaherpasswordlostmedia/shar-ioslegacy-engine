#!/bin/bash
# Гейт Г4 / правка 142: провалы Гомера под мир (ночь ботов 30.09→01.10, топ-20 мест + 65/95/143). Сначала красный:
# сборка с -DHOMER_VOID_WALL=0 и мир ботов с BW_NO_DEATH=1 обязаны проваливаться на тех же повторах, нынешний код — нет,
# и на соседних вариантах ввода тоже (tests/falls/check.py). Мак, CPU, без эмулятора. tests/falls/run.sh -> PASS/FAIL
set -u
cd "$(dirname "$0")/../.."
O=build/tmp/falls; mkdir -p "$O"
BINS=game_headless OUT_DIR=$O/green tools/bots/build.sh >/dev/null || { echo "сборка: FAIL"; exit 1; }
BINS=game_headless OUT_DIR=$O/red tools/bots/build.sh -DHOMER_VOID_WALL=0 >/dev/null || { echo "сборка красной: FAIL"; exit 1; }
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY tests/falls/check.py $O/green/game_headless $O/red/game_headless

#!/bin/bash
# Гейт правки 142 / ДОБИВКА 13: «над пустотой без шага» — пол на высоте ближайшей опоры (viewer/homer.c voidFloor).
# Сборка мира ботов как есть и с -DHOMER_VOID_FLOOR_OLD=1 (красная: как до правки), повторы tests/bots/regress/vf_*.in
# (ночи 30.09–07.10, L1 J14-3 / J14-6 / K14-1) и «стена главнее края» (L1 F10-8, повтор vt_*.in, красная -DHOMER_VOID_SQUEEZE_OLD=1).
# Мак, CPU, без эмулятора.
#   tests/falls/void_floor.sh -> PASS / FAIL (tests/falls/void_floor.py)
set -u
cd "$(dirname "$0")/../.."
O=build/tmp/void_floor; mkdir -p "$O"
BINS="game_headless probe" OUT_DIR=$O/green tools/bots/build.sh >/dev/null || { echo "сборка: FAIL"; exit 1; }
BINS=game_headless OUT_DIR=$O/red tools/bots/build.sh -DHOMER_VOID_FLOOR_OLD=1 >/dev/null || { echo "сборка красной: FAIL"; exit 1; }
BINS=game_headless OUT_DIR=$O/red_sq tools/bots/build.sh -DHOMER_VOID_SQUEEZE_OLD=1 >/dev/null || { echo "сборка красной F10-8: FAIL"; exit 1; }
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY tests/falls/void_floor.py $O/green/game_headless $O/red/game_headless $O/green/probe $O/red_sq/game_headless

#!/bin/bash
# Гейт правки 349 (зоны DEATH: все объёмы локатора, курс точки возврата) без эмулятора: данные диска + мир ботов.
#   tests/death/run.sh [LEVEL]   LEVEL — уровень 1 с блоком JMP1 правки 349 (по умолчанию build/level.shr) -> PASS / FAIL
# Красный: тот же check.py на прежнем коде и уровне (game_headless из git HEAD до правки, build/level.shr до пересборки) — падает
# (D4: старый блок JMP1; B1/B4: ящик 1 двора покрышек и Гомер пешком не переносят). Показ (затемнение) — tests/death/emu_check.py
set -u
cd "$(dirname "$0")/../.."
O=build/tmp/death; mkdir -p "$O"
BINS=game_headless OUT_DIR=$O tools/bots/build.sh >/dev/null || { echo "сборка: FAIL"; exit 1; }
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY tests/death/check.py $O/game_headless "${1:-build/level.shr}"

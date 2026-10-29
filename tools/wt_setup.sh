#!/bin/bash
# Копия репозитория для агента (git worktree): тулчейн, venv и данные диска — ссылками на основную копию; свой build/ —
# клонами файлов основного (APFS cp -c: мгновенно, места не занимает). В основной build/ агент не пишет никогда: выпуск
# (tools/ship.sh), выкладка на PSP и PSPLink — только терминал. Запуск: bash tools/wt_setup.sh из корня копии
MAIN=$HOME/Downloads/shar-psp
cd "$(git rev-parse --show-toplevel)" || exit 1
[ "$(cd "$PWD" && pwd -P)" = "$(cd "$MAIN" && pwd -P)" ] && { echo "wt_setup: это основная копия, не агентская"; exit 1; }
for d in pspdev .venv hit-and-run-web donut; do   # donut — сигнатуры команд миссий (tools/missions/commands.py, гейты tests/ui)
 [ -e "$d" ] || ln -s "$MAIN/$d" "$d"; done
mkdir -p build
for f in "$MAIN"/build/*; do   # файлы верхнего уровня: уровень, пакеты, EBOOT, служебные таблицы
  [ -f "$f" ] || continue; b=$(basename "$f"); [ -e "build/$b" ] || cp -c "$f" "build/$b" 2>/dev/null || cp "$f" "build/$b"
done
for d in audio chars movies missions sandbox levels assets ui ps2ref objlvl; do   # папки данных движка, ботов и эталона
  [ -d "$MAIN/build/$d" ] && [ ! -e "build/$d" ] && cp -cR "$MAIN/build/$d" "build/$d"
done
mkdir -p build/bots build/tmp_conv
echo "wt_setup: готово — $(ls build | wc -l | tr -d ' ') записей в build/, ссылки: pspdev .venv hit-and-run-web donut"

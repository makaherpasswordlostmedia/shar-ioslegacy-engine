#!/bin/bash
# Стенд SHARBENCH на PSP (bench/main.c): отдельная папка PSP/GAME/SHARBENCH, игру SHARVIEW не трогает.
#   tools/bench_psp.sh --deploy   собрать стенд и положить на PSP (сверка cmp)
#   tools/bench_psp.sh --fetch    забрать bench.txt с PSP в build/bench/sharbench_<время>.txt и показать
set -e
cd "$(dirname "$0")/.."
D=/Volumes/PSP/PSP/GAME/SHARBENCH
if [ ! -d /Volumes/PSP/PSP ]; then echo "подключи PSP по USB"; exit 1; fi
case "$1" in
  --deploy)
    export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:$PATH
    psp-cmake -S bench -B bench/build > /dev/null && cmake --build bench/build > /dev/null
    mkdir -p "$D" && cp bench/build/EBOOT.PBP "$D/EBOOT.PBP" && cmp bench/build/EBOOT.PBP "$D/EBOOT.PBP"
    echo "SHARBENCH на PSP: $(shasum -a 256 "$D/EBOOT.PBP" | cut -c1-8)" ;;
  --fetch)
    [ -f "$D/bench.txt" ] || { echo "на PSP нет bench.txt: стенд ещё не запускали"; exit 1; }
    mkdir -p build/bench && F=build/bench/sharbench_$(date +%Y%m%d-%H%M).txt && cp "$D/bench.txt" "$F" && cat "$F" && echo "→ $F" ;;
  *) echo "tools/bench_psp.sh --deploy | --fetch"; exit 2 ;;
esac

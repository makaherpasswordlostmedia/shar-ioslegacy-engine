#!/bin/bash
# Гейт правки Роба 263 (заменила 205): под заставкой нет темы уровня 1, только звук включения. КРАСНЫЙ: -DBOOT_MUSIC_205=1 (тема под заставкой) обязан упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; PY="$ROOT/.venv/bin/python"; OUT=build/bootmusic; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DBOOT_MUSIC_205=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка"; exit 2; }
"$PY" tests/bootsnd/music_run.py red "$OUT/red_build/EBOOT.PBP" > "$OUT/red.txt" 2>&1; rr=$?; tail -1 "$OUT/red.txt"
"$PY" tests/bootsnd/music_run.py green "${BOOT_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/green.txt" 2>&1; rg=$?; tail -1 "$OUT/green.txt"
[ $rr -ne 0 ] && [ $rg -eq 0 ] && echo "PASS: красный пойман, зелёный — под заставкой музыки игры нет" || { echo "FAIL"; exit 1; }

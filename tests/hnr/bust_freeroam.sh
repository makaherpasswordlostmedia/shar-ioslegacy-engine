#!/bin/bash
# Гейт правки Роба 227 («после поимки отвезли на первую миссию заново — у оригинала просто штраф»): арест в свободной езде —
# штраф, без провала миссии. КРАСНЫЙ: EBOOT с -DBUSTED_FREEROAM_FAILS=1 -DBUST_FAILS_MISSION_OLD=1 (прежнее) обязан упасть. ЗЕЛЁНЫЙ: viewer/build/EBOOT.PBP
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/bust_freeroam; mkdir -p "$OUT"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
psp-cmake -S viewer -B "$OUT/red_build" -DCMAKE_C_FLAGS="-DBUSTED_FREEROAM_FAILS=1 -DBUST_FAILS_MISSION_OLD=1" > "$OUT/red_cmake.txt" 2>&1 &&
  cmake --build "$OUT/red_build" > "$OUT/red_build.txt" 2>&1 || { echo "FAIL: красная сборка не собралась"; exit 2; }
"$PY" tests/hnr/bust_freeroam.py red "$OUT/red_build/EBOOT.PBP" > "$OUT/red.txt" 2>&1; rr=$?; tail -1 "$OUT/red.txt"
if [ $rr -ne 0 ] && grep -q "провал миссии=True" "$OUT/red.txt"; then echo "красный (-DBUSTED_FREEROAM_FAILS=1 -DBUST_FAILS_MISSION_OLD=1): упал, как должен"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
"$PY" tests/hnr/bust_freeroam.py green "${BUST_EBOOT:-viewer/build/EBOOT.PBP}" > "$OUT/green.txt" 2>&1; rg=$?; tail -1 "$OUT/green.txt"
if [ $red -eq 1 ] && [ $rg -eq 0 ]; then echo "PASS: красный пойман, зелёный — штраф без провала"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rg"; exit 1

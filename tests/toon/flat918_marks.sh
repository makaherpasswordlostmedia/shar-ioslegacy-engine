#!/bin/bash
# Гейт №918: «разметка видна везде, где была» (тонкая разметка земли L1 после заливки). tests/toon/flat918_marks.sh EBOOT.PBP НАБОР [ВЫХОД]
# НАБОР — как у flat912.sh (flat912.bin с правилом тонкой разметки, tools/flat_list.py причина 7). Красный контроль: тот же гейт на наборе со старым flat912.bin (набор до №918) — должен упасть.
set -u
cd "$(dirname "$0")/../.."; ROOT=$PWD
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; OUT=${3:-$ROOT/build/flat918_gate/$(date +%H%M%S)}
mkdir -p "$OUT"; TMP="$ROOT/build/flat918_pkg_$$"; trap 'rm -rf "$TMP"' EXIT
cp -cR "$PK" "$TMP" 2>/dev/null || cp -R "$PK" "$TMP"; cp "$EB" "$TMP/EBOOT.PBP"
( SMOKE_HOME="$OUT/home" SMOKE_EXTRA="notoon.txt flat912.bin marks912.bin" SMOKE_FLAGS="" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$ROOT/tests/toon/flat918_marks_scenario.txt" SMOKE_MAXT=420 tools/smoke.sh "$TMP" > "$OUT/smoke.out" 2>&1 )
D="$ROOT/$(grep -o "build/smoke/[0-9-]*" "$OUT/smoke.out" | head -1)"; [ -d "$D" ] || { echo "FAIL нет папки прогона смоука"; exit 2; }; rm -rf "$OUT/run"; cp -R "$D" "$OUT/run"
python3 "$ROOT/tests/toon/flat918_marks_check.py" "$OUT/run"

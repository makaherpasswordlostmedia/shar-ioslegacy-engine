#!/bin/bash
# №666/№667: прогон сценария посадки в безголовом эмуляторе на полном наборе данных (все уровни 1–7 из DATA).
#   tests/seat/run.sh СЦЕНАРИЙ [DATA=build/data] [EBOOT=viewer/build/EBOOT.PBP] [ФЛАГИ-ФАЙЛЫ через SEAT_FLAGS="a b"]
# Итог: build/seat/<время>/ (smoke.txt, снимки png). Очередь эмуляторов: не больше 5 (pgrep -x PPSSPPHeadless).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCN="$1"; DATA="${2:-$ROOT/build/data}"; EB="${3:-$ROOT/viewer/build/EBOOT.PBP}"
while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 5; done
STAMP=$(date +%Y%m%d-%H%M%S); RUN="$ROOT/build/emu/seat/$STAMP-$$"; OUT="$ROOT/build/seat/$STAMP-$$"
mkdir -p "$RUN" "$OUT"; trap 'rm -rf "$RUN"' EXIT
cp -cR "$DATA"/. "$RUN"/ 2>/dev/null || cp -R "$DATA"/. "$RUN"/
cp "$EB" "$RUN/EBOOT.PBP"; cp "$SCN" "$RUN/scenario.txt"; touch "$RUN/smokelog"
for f in ${SEAT_FLAGS:-}; do touch "$RUN/$f"; done
MAXT=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=1} END{print int(s)+90}' "$SCN"); MAXT="${SMOKE_MAXT:-$MAXT}"
python3 "$ROOT/tools/smoke_headless.py" "$RUN" "$OUT" "$MAXT"
cp "$RUN/smoke.txt" "$OUT/" 2>/dev/null
echo "$OUT"

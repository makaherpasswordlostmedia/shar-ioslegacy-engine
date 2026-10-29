#!/bin/bash
# Гейт памяти TEST57 В (окно «Оптимизация»): куча и наибольший кусок кучи на сценах тура не ниже TEST55, отказов памяти 0. Безголовый эмулятор, своя папка эмулятора.
#   tests/mem/heap57.sh EBOOT.PBP НАБОР [ВЫХОД]      НАБОР — папка набора тура (как build/test57tour/PSP/GAME/SHARTEST15)
# Сценарий: HEAP57_SCN=файл (по умолчанию heap57_scenario.txt — стоя; heap57_scenario_drive.txt — с ездой flag drive: кучу ест догрузка клеток при езде, с TEST55 несопоставимо, TEST55 тогда ездил вхолостую)
# Красный контроль: HEAP57_RED=1 — EBOOT собран с -DLEVEL_TAIL_OLD=1 (хвост таблиц в участке, прежний LVA_BYTES) — гейт обязан упасть
set -u
cd "$(dirname "$0")/../.."; ROOT=$PWD
EB=${1:?EBOOT.PBP}; SET=${2:?НАБОР}; OUT=${3:-$ROOT/build/heap57_gate/$(date +%H%M%S)}
BIN=${PPSSPP_HEADLESS:-$ROOT/build/twins/bin/PPSSPPHeadless}
mkdir -p "$OUT/home" "$OUT/out"; RUN="$OUT/run"; cp -cR "$SET" "$RUN" 2>/dev/null || cp -R "$SET" "$RUN"
cp "$EB" "$RUN/EBOOT.PBP"; SCN=${HEAP57_SCN:-tests/mem/heap57_scenario.txt}; cp "$SCN" "$RUN/scenario.txt"; : > "$RUN/smokelog"
MAXT=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=1} END{print int(4*s)+300}' "$SCN")   # 4×+300 с: под нагрузкой Мака (night_loop) эмулятор идёт медленнее, иначе недостающие сцены дают ложный ПРОВАЛ (Надзор 24.10)
( cd "$RUN" && HOME="$OUT/home" TWINS_SMOKE="$RUN/smoke.txt" TWINS_SHOTDIR="$OUT/out" SDL_AUDIODRIVER=dummy XDG_CONFIG_HOME="$OUT/out/config" XDG_DATA_HOME="$OUT/out/data" \
  "$BIN" --graphics=software --timeout=$MAXT "$RUN/EBOOT.PBP" > "$OUT/out/headless.log" 2>&1 )
python3 tests/mem/heap57_check.py "$RUN/smoke.txt"; RC=$?
if [ -n "${HEAP57_RED:-}" ]; then if [ $RC -ne 0 ]; then echo "КРАСНЫЙ КОНТРОЛЬ: упал, как должен"; exit 0; else echo "КРАСНЫЙ КОНТРОЛЬ: гейт не упал на прежнем поведении"; exit 1; fi; fi
exit $RC

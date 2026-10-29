#!/bin/bash
# Машина уровня в эмуляторе (29.09): короткая езда, выход и посадка на уровне N — один запуск PPSSPP через общую очередь
# tools/ppsspp_run.sh (одно окно, короткий прогон). Данные — набор уровня 1 (DIR, как у смоука) и для N > 1 папка
# l<N>/ (level.shr, fx.shr, ui.shr, traffic.shr, audio/) плюс спутники с номером в корне — как их ищет движок (main.c levelFile).
#   tests/cars/emu.sh N [DIR]          DIR — EBOOT.PBP и данные уровня 1 (по умолчанию build/ship_stage)
#   tests/cars/emu.sh --negative N     красный: движку подложен level.shr с CAR1 версии 1 (без машины) — строка CAR должна
#                                      показать famil_v не своего уровня, проверка обязана упасть
# Проверка tests/cars/emu_check.py: машина уровня прочитана из CAR1 (имя = InitLevelPlayerVehicle), разгон прямо, выход △ и
# посадка △, свободная куча на старте ≥ 20 МБ, ровные 30 FPS сцен езды.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
N="${1:?уровень}"; SRC="${2:-build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$ROOT/$SRC" ;; esac
L=build/levels/l$N
STAMP=$(date +%Y%m%d-%H%M%S); RUN="$ROOT/build/emu/cars/$STAMP-$$"; OUT="$ROOT/build/gates/cars/emu_l${N}_$STAMP"; mkdir -p "$RUN" "$OUT"
trap 'rm -rf "$RUN"' EXIT
cp -c "$SRC/EBOOT.PBP" "$RUN/" 2>/dev/null || cp "$SRC/EBOOT.PBP" "$RUN/"
for f in $(tools/ship_files.sh); do [ -f "$SRC/$f" ] || { echo "нет $SRC/$f"; exit 1; }; mkdir -p "$RUN/$(dirname "$f")"; cp -c "$SRC/$f" "$RUN/$f" 2>/dev/null || cp "$SRC/$f" "$RUN/$f"; done
SHR="$L/level.shr"; [ $NEG = 1 ] && SHR="$L/level_pre_car1v2.shr"
if [ "$N" != 1 ]; then
  mkdir -p "$RUN/l$N"
  cp -c "$SHR" "$RUN/l$N/level.shr"; for f in fx.shr ui.shr traffic.shr; do cp -c "$L/$f" "$RUN/l$N/$f"; done; cp -cR "$L/audio" "$RUN/l$N/"
  for f in interiors-l$N.bin interiors-l$N-gfx.bin collect-l$N.shr zonecam-l$N.shr; do cp -c "$L/$f" "$RUN/$f"; done
  cp -c "$L/missions/level0$N.msn" "$RUN/level0$N.msn"
else cp -c "$SHR" "$RUN/level.shr"; fi
{ [ "$N" != 1 ] && echo "flag level $N"
  printf 'scene spawn\nwait 3\nflag carv\nshot spawn\nscene drive\nflag autostraight 3\nwait 1.5\nflag carv\nwait 1.5\nflag carv\nwait 2\nflag carv\nshot drive\nflag stop\n'
  printf 'scene exit\nwait 1\npress triangle\nwait 4\nflag carv\nshot exit\nscene enter\npress triangle\nwait 6\nflag carv\nshot enter\nend\n'; } > "$RUN/scenario.txt"
touch "$RUN/smokelog"
MAXT=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=1} END{print int(s)+90}' "$RUN/scenario.txt")
PPSSPP_SHOTS="$RUN/smoke.txt" PPSSPP_SHOTDIR="$OUT" tools/ppsspp_run.sh "$RUN/EBOOT.PBP" "$MAXT" > "$OUT/ppsspp.txt" 2>&1
cp "$RUN/smoke.txt" "$RUN/scenario.txt" "$OUT/" 2>/dev/null
echo "прогон: ${OUT#$ROOT/}"
.venv/bin/python tests/cars/emu_check.py "$OUT/smoke.txt" --level "$N"

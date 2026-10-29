#!/bin/bash
# Приёмка №934а (окно «Мосты», TEST60): ОДНА команда  tests/road934/accept60.sh  — сама собирает EBOOT тура (со смоуком) и красный EBOOT (-DFARROAD934_OLD=1),
# сверяет выданные данные (build/t60/data_most, побайтно с чистым экспортом), гоняет гейт tests/road934/road934.sh на 7 уровнях (данные, кадр, безголовый эмулятор через tools/emu_run.sh) и зелёным, и красным.
# Последняя строка: «ПРИЁМКА №934а: PASS» или «ПРИЁМКА №934а: FAIL». Пределы: ≤ 3000 треугольников в кадре, ≤ 0,15 мс PSP (медиана avg_us ≤ 26 мкс Мака), ≤ 120000 Б на уровень, IoU ≥ 0,98 (допуск 1 px).
#   переменные: SET (набор данных, по умолчанию тур TEST59), DATA (папка выданных данных), LEVELS, OUT (куда класть результаты прогона), NOBUILD=1 (EBOOT уже собраны)
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PATH="$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH"; export PSPDEV="$W/pspdev"; export PATH="$W/pspdev/bin:$PATH"
PY="${PY:-$HOME/Downloads/shar-psp/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SETD="${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}"
DATA="${DATA:-$HOME/Downloads/shar-psp/build/t60/data_most}"
LEVELS="${LEVELS:-1 2 3 4 5 6 7}"
OUT="${OUT:-$W/build/accept60_most}"; mkdir -p "$OUT"
BASEFLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
fail=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
if [ "${NOBUILD:-0}" != 1 ]; then
  say "сборка EBOOT тура (со смоуком): viewer/build_t60"
  (cd viewer && psp-cmake -S . -B build_t60 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEFLAGS" > "$OUT/cfg_green.log" 2>&1 && cmake --build build_t60 -j4 > "$OUT/build_green.log" 2>&1) || { echo "сборка зелёного EBOOT упала: $OUT/build_green.log"; echo "ПРИЁМКА №934а: FAIL"; exit 1; }
  say "сборка красного EBOOT (-DFARROAD934_OLD=1): viewer/build_t60_red"
  (cd viewer && psp-cmake -S . -B build_t60_red -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEFLAGS -DFARROAD934_OLD=1" > "$OUT/cfg_red.log" 2>&1 && cmake --build build_t60_red -j4 > "$OUT/build_red.log" 2>&1) || { echo "сборка красного EBOOT упала: $OUT/build_red.log"; echo "ПРИЁМКА №934а: FAIL"; exit 1; }
fi
EB="$W/viewer/build_t60/EBOOT.PBP"; EBR="$W/viewer/build_t60_red/EBOOT.PBP"
[ -f "$EB" ] && [ -f "$EBR" ] || { echo "нет EBOOT: $EB / $EBR"; echo "ПРИЁМКА №934а: FAIL"; exit 1; }
# красный EBOOT обязан отличаться от зелёного (флаг доехал до сборки)
cmp -s "$EB" "$EBR" && { echo "красный EBOOT совпал с зелёным: флаг не сработал"; echo "ПРИЁМКА №934а: FAIL"; exit 1; }
say "данные: чистый экспорт против выданных ($DATA)"
LVSRC="${LV_SRC:-$HOME/Downloads/shar-psp-urovni-w/build/reissue7}"
export ROAD934_NAMES="${ROAD934_NAMES:-$W/build/roads/texnames.json}"
[ -f "$ROAD934_NAMES" ] || { mkdir -p "$(dirname "$ROAD934_NAMES")"; "$PY" -c "import sys; sys.path.insert(0,'tools'); import notoon_list as N; N.names_by_digest('$ROAD934_NAMES')" > /dev/null 2>&1; }
for L in $LEVELS; do
  if [ "$L" = 1 ]; then D="$DATA/road934.shr"; else D="$DATA/l$L/road934.shr"; fi
  "$PY" tools/road934_export.py "$LVSRC/l$L/level.shr" "$OUT/fresh_l$L.shr" > /dev/null 2>&1
  if cmp -s "$OUT/fresh_l$L.shr" "$D"; then echo "L$L: выданные данные = чистый экспорт ($(stat -f %z "$D") Б)"; else echo "L$L: выданные данные НЕ совпали с чистым экспортом ($D)"; fail=1; fi
done
say "гейт tests/road934/road934.sh"
RED_LEVELS="${RED_LEVELS:-${LEVELS%% *}}" OUT="$OUT/emu" EMU_OWNER=most EB_RED="$EBR" tests/road934/road934.sh "$DATA" "$EB" "$SETD" $LEVELS | tee "$OUT/gate.txt"
grep -q "^ГЕЙТ №934: PASS" "$OUT/gate.txt" || fail=1
[ $fail = 0 ] && { echo "ПРИЁМКА №934а: PASS"; exit 0; }; echo "ПРИЁМКА №934а: FAIL"; exit 1

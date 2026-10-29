#!/bin/bash
# Гейт правки Роба 135 (звуки ударов и разрушений): tests/sfx135/host.c на настоящих sound.c/audio.c/car.c/col.c/stateprops.c,
# пакете звука уровня 1 и level.shr (Мак, CPU, без эмулятора). Сначала КРАСНЫЙ: код базы dfb0441 (до правки 135) обязан упасть
# на 135.1–135.6; новый код без журнала (-DNOLOG) — только на 135.7. Потом ЗЕЛЁНЫЙ. Итог: build/sfx135/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/sfx135; mkdir -p "$OUT"; PACK=${SFX_PACK:-build/audio/}; LEVEL=${SFX_LEVEL:-build/level.shr}; BASE=${SFX_BASE:-dfb0441}
rm -rf "$OUT/old"; mkdir -p "$OUT/old"; git archive "$BASE" viewer | tar -x -C "$OUT/old"
build() {   # $1 имя, $2 папка viewer, дальше флаги
  local n=$1 V=$2; shift 2
  cc -std=c11 -O1 -w -DAUDIO_HOST -DSKIN_HOST "$@" -I "$V" -c "$V/sound.c" -DaudioPlay=hookPlay -o "$OUT/sound_$n.o" 2> "$OUT/build_$n.txt" &&
  cc -std=c11 -O1 -w -DAUDIO_HOST -DSKIN_HOST "$@" -I "$V" tests/sfx135/host.c "$OUT/sound_$n.o" "$V/audio.c" "$V/car.c" "$V/col.c" \
     "$V/props.c" "$V/stateprops.c" "$V/coins.c" "$V/homer.c" "$V/skin.c" -lm -o "$OUT/host_$n" 2>> "$OUT/build_$n.txt" ||
  { echo "FAIL: сборка $n"; head -5 "$OUT/build_$n.txt"; exit 1; }
}
red=0
build old "$OUT/old/viewer" -DOLD; "$OUT/host_old" "$PACK" "$LEVEL" > "$OUT/red_old.txt" 2>&1; rc=$?
fl=$(grep -c "^FAIL" "$OUT/red_old.txt")
if [ $rc -ne 0 ] && [ "$fl" -ge 6 ]; then echo "красный (код до правки 135): упал, как должен — $fl проверок"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: старый код — rc=$rc, провалов $fl (нужно >= 6)"; fi
grep "^FAIL" "$OUT/red_old.txt" | cut -c1-100 | sed 's/^/   /'
build nolog viewer -DNOLOG; "$OUT/host_nolog" "$PACK" "$LEVEL" > "$OUT/red_nolog.txt" 2>&1; rc=$?
if [ $rc -ne 0 ] && grep -q "^FAIL 135.7" "$OUT/red_nolog.txt" && [ "$(grep -c '^FAIL' "$OUT/red_nolog.txt")" -eq 1 ]; then
  echo "красный (без журнала sfxlog): упал только на 135.7, как должен"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: без журнала rc=$rc"; grep "^FAIL" "$OUT/red_nolog.txt"; fi
build air viewer -DSND_CAR_AIR=1; "$OUT/host_air" "$PACK" "$LEVEL" > "$OUT/red_air.txt" 2>&1; rc=$?   # 135.9: гул в полёте включён
if [ $rc -ne 0 ] && grep -q "^FAIL 135.9" "$OUT/red_air.txt"; then echo "красный (гул в полёте включён): упал на 135.9, как должен"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: гул в полёте rc=$rc"; fi
build new viewer; "$OUT/host_new" "$PACK" "$LEVEL" > "$OUT/green.txt" 2>&1; rc=$?
grep "FAIL\|RESULT" "$OUT/green.txt"
if [ $red -eq 3 ] && [ $rc -eq 0 ]; then echo "PASS: красный 3/3 пойман, зелёный $(grep -c '^OK' "$OUT/green.txt") проверок"; exit 0; fi
echo "FAIL: красный $red/3, зелёный rc=$rc"; exit 1

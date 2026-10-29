#!/bin/bash
# Гейт правки Роба 250 («эффекты слишком громкие — свести, как в оригинале»): уровни ударов, мотора и щелчка передачи против музыки
# на выходе настоящего микшера порта (viewer/sound.c + viewer/audio.c, AUDIO_HOST) с пакетом звука уровня 1. Мак, CPU, без эмулятора.
# Эталоны оригинала и откуда они — в шапке tests/sfx250/host.c и в правке 250 (docs/handoff/ПРАВКИ_РОБА.md).
#   КРАСНЫЙ 1: прежнее сведение (-DSND_250_OLD=1) обязано упасть на 250.1, 250.2, 250.3, 250.7, 250.8
#   КРАСНЫЙ 2: подмены по одной — потолок удара без замера (COLL_VMAX=1) -> 250.2; мотор прежний (ENG_250_GAIN=1) -> 250.7 + 250.8 (проекция мотора на gearshift)
#   ЗЕЛЁНЫЙ: новое сведение — все проверки
# Итог: build/sfx250/{red_old,red_vmax,red_eng,green}.txt; код 0 — красные пойманы и зелёный прошёл
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/sfx250; mkdir -p "$OUT"; PACK=${SFX_PACK:-build/audio/}
[ -f "$PACK/sfx.sab" ] && [ -f "$PACK/music.sap" ] || { echo "FAIL: нет пакета звука $PACK (sfx.sab, music.sap)"; exit 2; }
build() {   # $1 имя, дальше флаги cc
  local n=$1; shift
  cc -std=c11 -O2 -w -DAUDIO_HOST "$@" -I viewer tests/sfx250/host.c viewer/sound.c viewer/audio.c -lm -o "$OUT/host_$n" \
     2> "$OUT/build_$n.txt" || { echo "FAIL: сборка $n"; head -5 "$OUT/build_$n.txt"; exit 2; }
}
red=0
expect_red() {   # $1 имя, $2 список проверок, которые обязаны упасть
  local n=$1 want=$2 got; "$OUT/host_$n" "$PACK" > "$OUT/red_$n.txt" 2>&1; local rc=$?
  got=$(grep "^FAIL" "$OUT/red_$n.txt" | awk '{print $2}' | tr '\n' ' ' | sed 's/ $//')
  if [ $rc -ne 0 ] && [ "$got" = "$want" ]; then echo "красный ($n): упал на $got — как должен"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН ($n): rc=$rc, упали [$got], нужно [$want]"; fi
}
build old -DSND_250_OLD=1;      expect_red old "250.1 250.2 250.3 250.7 250.8"
build vmax -DCOLL_VMAX=1.f;     expect_red vmax "250.2 250.3 250.5"
build eng -DENG_250_GAIN=1.f;   expect_red eng "250.7 250.8"
build new; "$OUT/host_new" "$PACK" > "$OUT/green.txt" 2>&1; rc=$?
grep -v "^OK" "$OUT/green.txt"
"$OUT/host_old" "$PACK" demo "$OUT/demo_old.wav" > /dev/null; "$OUT/host_new" "$PACK" demo "$OUT/demo_new.wav" > /dev/null   # на слух
if [ $red -eq 3 ] && [ $rc -eq 0 ]; then echo "PASS: красный 3/3 пойман, зелёный $(grep -c '^OK' "$OUT/green.txt") проверок"; exit 0; fi
echo "FAIL: красный $red/3, зелёный rc=$rc"; exit 1

#!/bin/bash
# Гейт громкости фона (аудит 09.10 п. 22, правка Роба 161): уровни в дБ на выходе настоящего микшера порта (viewer/sound.c +
# viewer/audio.c, AUDIO_HOST) с пакетом звука уровня 1 против записи PS2 В25 (knowledge/facts/ps2-ambience-level.yaml). Мак, CPU.
#   КРАСНЫЙ 1: прежний код (-DAMB161_OLD=1) обязан упасть на 161.4 (и 422.2 — комната меряется тем же тюнером) — множитель 0,6 затирается набором шин режима, на выходе 0,70
#   КРАСНЫЙ 2: множитель 0,6 «на слух», если бы он действовал (-DAMB_GAIN=.6f) — обязан упасть на 161.2 161.3 (на 6,6 дБ тише PS2)
#   КРАСНЫЙ 3: без шага 422 (-DAMB422_OLD=1, улица как PS2) — обязан упасть ровно на 422.1 (вкус Роба 09.10: улица −3 дБ)
#   ЗЕЛЁНЫЙ: все проверки (161.2–161.4 — с ожиданием, сдвинутым на шаг 422 этой сборки)
# Итог: build/amb161/{red_old,red_g06,green}.txt; код 0 — красные пойманы и зелёный прошёл
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/amb161; mkdir -p "$OUT"; PACK=${SFX_PACK:-build/audio/}
[ -f "$PACK/sfx.sab" ] && [ -f "$PACK/music.sap" ] || { echo "FAIL: нет пакета звука $PACK (sfx.sab, music.sap)"; exit 2; }
build() { local n=$1; shift
  cc -std=c11 -O2 -w -DAUDIO_HOST "$@" -I viewer tests/amb161/host.c viewer/sound.c viewer/audio.c -lm -o "$OUT/host_$n" \
     2> "$OUT/build_$n.txt" || { echo "FAIL: сборка $n"; head -5 "$OUT/build_$n.txt"; exit 2; }
}
red=0
expect_red() { local n=$1 want=$2 got; "$OUT/host_$n" "$PACK" > "$OUT/red_$n.txt" 2>&1; local rc=$?
  got=$(grep "^FAIL" "$OUT/red_$n.txt" | awk '{print $2}' | tr '\n' ' ' | sed 's/ $//')
  if [ $rc -ne 0 ] && [ "$got" = "$want" ]; then echo "красный ($n): упал на $got — как должен; $(grep -m1 'AMB_GAIN' "$OUT/red_$n.txt")"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН ($n): rc=$rc, упали [$got], нужно [$want]"; fi
}
build old -DAMB161_OLD=1; expect_red old "161.4 422.2"
build g06 -DAMB_GAIN=.6f; expect_red g06 "161.2 161.3"
build o422 -DAMB422_OLD=1; expect_red o422 "422.1"
build new; "$OUT/host_new" "$PACK" > "$OUT/green.txt" 2>&1; rc=$?
cat "$OUT/green.txt"
if [ $red -eq 3 ] && [ $rc -eq 0 ]; then echo "PASS: красный 3/3 пойман, зелёный $(grep -c '^OK' "$OUT/green.txt") проверок"; exit 0; fi
echo "FAIL: красный $red/3, зелёный rc=$rc"; exit 1

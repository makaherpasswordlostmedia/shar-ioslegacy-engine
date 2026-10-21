#!/bin/bash
# Голоса вождения пяти героев: прежняя привязка к Гомеру должна упасть у четырёх остальных
set -eu
cd "$(dirname "$0")/../.."
O=build/driver-gate; mkdir -p "$O"
cc -O2 -w -DAUDIO_HOST -I viewer tests/sound/driver_host.c viewer/sound.c viewer/audio.c -lm -o "$O/green"
cc -O2 -w -DAUDIO_HOST -DSOUND_DRIVER_OLD -I viewer tests/sound/driver_host.c viewer/sound.c viewer/audio.c -lm -o "$O/red"
for code in hom brt lis mrg apu; do
  P="${DRIVER_PACK_ROOT:-$O}/$code"
  if [ -z "${DRIVER_PACK_ROOT:-}" ]; then python3 tests/sound/pcsay_synth.py "$P" --code "$code" --driver-events > /dev/null; fi
  "$O/green" "$P/" "$code"
  if [ "$code" != hom ]; then
    if "$O/red" "$P/" "$code" > "$O/red_$code.txt"; then echo "FAIL: красный $code не пойман"; exit 1; fi
    grep -q '^FAIL driver=' "$O/red_$code.txt" || { echo 'FAIL: красный не дошёл до проверки'; exit 1; }
  fi
done
echo 'PASS: все пять героев; четыре отрицательных контроля'

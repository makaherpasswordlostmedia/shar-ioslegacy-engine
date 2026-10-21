#!/bin/bash
# Правка 252: гейт NaN-предохранителя машины (viewer/car.c carFinite) в мире ботов на Маке. Зелёный — машина с NaN возвращена
# на надёжное место (NANHOST finite=1); красный контроль — сборка -DCAR_NAN_OLD (прежнее) обязана упасть (finite=0).
#   tests/crash_f10/nan.sh [level.shr] [homer.shr]
set -u; cd "$(dirname "$0")/../.."
V=viewer; . tools/bots/lib.sh; O=build/crash_f10; mkdir -p "$O"
LV="${1:-build/level.shr}"; HM="${2:-build/homer.shr}"
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I $V -I tools/bots"
$CC tests/crash_f10/nan_host.c $BOTS_LIB -lm -o "$O/nan_host" && $CC -DCAR_NAN_OLD tests/crash_f10/nan_host.c $BOTS_LIB -lm -o "$O/nan_host_old" \
  || { echo "FAIL: сборка"; exit 2; }
if "$O/nan_host_old" "$LV" "$HM" > "$O/nan_red.txt"; then echo "КРАСНЫЙ НЕ ПОЙМАН: $(cat "$O/nan_red.txt")"; exit 1; fi
echo "красный (CAR_NAN_OLD): $(grep NANHOST "$O/nan_red.txt") — упал, как должен"
"$O/nan_host" "$LV" "$HM" > "$O/nan_green.txt" || { echo "FAIL: $(cat "$O/nan_green.txt")"; exit 1; }
echo "зелёный: $(grep NANHOST "$O/nan_green.txt")"; echo "crash_f10/nan: PASS"

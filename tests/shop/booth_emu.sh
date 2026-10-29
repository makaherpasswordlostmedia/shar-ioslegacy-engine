#!/bin/bash
# Телефонная будка (правка Роба 104) в эмуляторе: будка R1P2, страница PhoneBooth.scr, картинки машин cars2d у открытой и закрытой.
#   tests/shop/booth_emu.sh [DIR]              зелёный: строки PHONEV/PHONE и картинки на снимках (tests/shop/booth_check.py)
#   tests/shop/booth_emu.sh --negative [DIR]   красный: тот же EBOOT с прежним пакетом build/phone_ok.shr (выпуск 30.09 11:50, до
#                                              f749b80: картинок нет — жалоба Роба) — сверка обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
if [ -n "$NEG" ]; then
  [ -f build/phone_ok.shr ] || { echo "FAIL: нет прежнего пакета build/phone_ok.shr для красного прогона"; exit 1; }
  cp "$SRC/EBOOT.PBP" "$T/EBOOT.PBP" && cp build/phone_ok.shr "$T/phone.shr" || exit 1; SRC="$T"
fi
L=$(SHIP_LEVELS="" SMOKE_SCN="$PWD/tests/shop/booth_scenario.txt" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
.venv/bin/python tests/shop/booth_check.py "$R" "$NEG"

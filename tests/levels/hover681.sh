#!/bin/bash
# №683: учёт реплик водителя уровня (SAYSTAT / SAY в журнале) на данных; tests/levels/hover681.sh EBOOT НАБОР [имя]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?}; PK=${2:?}; N=${3:-run}; T="$ROOT/build/gates/hover681/$N.$(date +%H%M%S)"; mkdir -p "$T"
cp -cR "$PK" "$T/pk" 2>/dev/null || cp -R "$PK" "$T/pk"; cp "$EB" "$T/pk/EBOOT.PBP"; rm -f "$T/pk/settings.bin"; [ -e "$T/pk/chars/male2.chr" ] || cp "$HOME/Downloads/shar-psp-sonnet-16b-w/build/test28tour/PSP/GAME/SHARTEST15/chars/male2.chr" "$T/pk/chars/"   # смоук требует; к репликам отношения нет
HB="$HOME/Downloads/.hover681_home.$$"; mkdir -p "$HB/.ppsspp/PSP/SAVEDATA"; trap 'rm -rf "$T/pk" "$HB"' EXIT
cp -R "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189700" "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189703" "$HB/.ppsspp/PSP/SAVEDATA/" 2>/dev/null
( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_HOME="$HB" SMOKE_FILEDATA="meaudio=3" SMOKE_SCN=tests/smoke_scenes/hover681.txt SMOKE_MAXT=400 tools/smoke.sh "$T/pk" ) > "$T/out" 2>&1
d="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/out" | tail -1)"; echo "$d"
ls "$d"/hv_*.png

#!/bin/bash
# Гейт №685: случайный звук не должен повторяться от запуска к запуску. tests/levels/seed685.sh EBOOT НАБОР
#   красный: два запуска БЕЗ семени (как было в игре) дают одинаковые реплики; зелёный: «flag sndseed 1» и «flag sndseed 2» дают разные
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?}; PK=${2:?}; T="$ROOT/build/gates/seed685/$(date +%H%M%S)"; mkdir -p "$T"
cp -cR "$PK" "$T/pk" 2>/dev/null || cp -R "$PK" "$T/pk"; cp "$EB" "$T/pk/EBOOT.PBP"; rm -f "$T/pk/settings.bin"; trap 'rm -rf "$T/pk"' EXIT
run() {  # имя семя
  HB="$HOME/Downloads/.seed685_home.$$.$1"; mkdir -p "$HB/.ppsspp/PSP/SAVEDATA"; cp -R "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189700" "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189703" "$HB/.ppsspp/PSP/SAVEDATA/" 2>/dev/null
  if [ -n "$2" ]; then sed "s/^flag repair\$/flag sndseed $2\nflag repair/" tests/smoke_scenes/seed685.txt > "$T/$1.txt"; else cp tests/smoke_scenes/seed685.txt "$T/$1.txt"; fi
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_HOME="$HB" SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$T/$1.txt" SMOKE_MAXT=300 tools/smoke.sh "$T/pk" ) > "$T/$1.out" 2>&1
  rm -rf "$HB"
  d="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"; grep -o "hist=[A-Za-z0-9_,]*" "$d/smoke.txt" | tail -1
}
run red_a "" > $T/a.o & run red_b "" > $T/b.o & wait; run s1 1 > $T/c.o & run s2 2 > $T/e.o & wait; a=$(cat $T/a.o); b=$(cat $T/b.o); c=$(cat $T/c.o); e=$(cat $T/e.o)
echo "красный: A=[$a] B=[$b]; зелёный: s1=[$c] s2=[$e]"
[ -n "$a" ] && [ "$a" = "$b" ] && [ "$c" != "$e" ] && { echo "SEED685: PASS"; exit 0; }
echo "SEED685: FAIL"; exit 1

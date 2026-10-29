#!/bin/bash
# Гейт №670 «подсказки Барта только в NEW GAME». RESUME сохранения Роба (копия в своём HOME), набор без settings.bin: 0 строк TUTORIAL on за 3 мин пешком и за рулём.
#   tests/levels/tut670.sh EBOOT НАБОР   красный: «flag tutresumeold 1» (прежнее поведение: маска из settings.bin = пусто) -> подсказки есть; NEW GAME: подсказка есть
# Первая строка вывода — итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T="$ROOT/build/gates/tut670/$(date +%H%M%S)"; mkdir -p "$T"
cp -cR "$PK" "$T/pk" 2>/dev/null || cp -R "$PK" "$T/pk"; cp "$EB" "$T/pk/EBOOT.PBP"; rm -f "$T/pk/settings.bin"
HB="$HOME/Downloads/.tut670_home.$$"; mkdir -p "$HB/.ppsspp/PSP/SAVEDATA"; trap 'rm -rf "$T/pk" "$HB"' EXIT
cp -R "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189700" "$HOME/.config/ppsspp/PSP/SAVEDATA/SLES5189703" "$HB/.ppsspp/PSP/SAVEDATA/" 2>/dev/null
run() {
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_HOME="$HB" SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$2" SMOKE_MAXT=300 tools/smoke.sh "$T/pk" ) > "$T/$1.out" 2>&1
  d="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)"
  echo "$(grep -c '^TUTORIAL on' "$d/smoke.txt") $(grep -c '^GAME n=' "$d/smoke.txt") $(grep -c 'FAULT' "$d/smoke.txt")"
}
{ echo "flag tutresumeold 1"; cat tests/levels/tut670_resume.txt; } > "$T/red.txt"
gr=$(run green_resume tests/levels/tut670_resume.txt); rr=$(run red_resume "$T/red.txt"); gn=$(run green_new tests/levels/tut670_new.txt)
set -- $gr; g=$1; ge=$2; gf=$3; set -- $rr; r=$1; set -- $gn; n=$1; ne=$2
[ "$g" = 0 ] && [ "$ge" -ge 1 ] && [ "$gf" = 0 ] && [ "$r" -ge 1 ] && [ "$n" -ge 1 ] && { echo "TUT670: PASS (RESUME TUT=$g GAME=$ge; красный TUT=$r; NEW TUT=$n)"; exit 0; }
echo "TUT670: FAIL (RESUME TUT=$g GAME=$ge FAULT=$gf; красный TUT=$r; NEW TUT=$n) $T"; exit 1

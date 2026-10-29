#!/bin/bash
# Гейт №696 «куча не тает при смене уровня». Цепочка L1 -> L7 -> L1 дважды (NEW GAME + QUIT GAME, служебный выбор уровня), безголовый эмулятор.
#   tests/levels/leak696.sh EBOOT НАБОР   НАБОР — папка с данными (копия набора теста, в ней ничего не меняется); сверка tests/levels/leak696_check.py
#   зелёный: свободная куча и крупнейший блок перед каждой загрузкой не падают больше чем на 0,2 МБ (по кругам), L7 col=1 traffic=1, allocfail 0
#   красный: «flag lvleak696old 1» (прежнее: счётчик листов DLBUILD и очередь отложенного освобождения были одной переменной dfN) — обязан упасть
# Первая строка вывода — итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; T="$ROOT/build/gates/leak696/$(date +%H%M%S)"; mkdir -p "$T"
cp -cR "$PK" "$T/pk" 2>/dev/null || cp -R "$PK" "$T/pk"; cp "$EB" "$T/pk/EBOOT.PBP"; rm -f "$T/pk/settings.bin"
HB="$HOME/Downloads/.leak696_home.$$"; mkdir -p "$HB/.ppsspp/PSP/SAVEDATA"; trap 'rm -rf "$T/pk" "$HB"' EXIT
run() {
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_HOME="$HB" SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$2" SMOKE_MAXT=900 tools/smoke.sh "$T/pk" ) > "$T/$1.out" 2>&1
  echo "$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/$1.out" | tail -1)/smoke.txt"
}
awk '{print} /^flag menu$/{print "flag lvleak696old 1"}' tests/levels/leak696_scenario.txt > "$T/red.txt"
g=$(run green tests/levels/leak696_scenario.txt); python3 tests/levels/leak696_check.py "$g" > "$T/green.log" 2>&1; gr=$?
r=$(run red "$T/red.txt"); python3 tests/levels/leak696_check.py "$r" > "$T/red.log" 2>&1; rr=$?
if [ $gr = 0 ] && [ $rr != 0 ]; then echo "LEAK696: PASS (зелёный: ни одного провала; красный поймал: $(grep -m1 ПРОВАЛ "$T/red.log" | cut -c1-110))"; cat "$T/green.log"; exit 0; fi
echo "LEAK696: FAIL (зелёный rc=$gr, красный rc=$rr) $T"; grep ПРОВАЛ "$T/green.log" | head -3; exit 1

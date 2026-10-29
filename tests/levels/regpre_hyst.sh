#!/bin/bash
# Гейт REGPRE-гистерезис. (1) хост-юнит tests/levels/regpre_unit.c на настоящей функции viewer/regpre.h: путь у границы GATE_PRE_M с шумом скорости и курса;
# красный = прежнее (hyst 0) обязан мигать (> 1 включения региона за 10 с), зелёный = гистерезис ≤ 1. (2) движок: первая ходьба NEW GAME L1 в безголовом эмуляторе —
# регион впрок всё ещё включается (REGPRE есть), не больше 1 включения на регион за 10 с, прогон OK. Переключатель прежнего в движке: REGPRE_HYST_OLD=1 / «flag regprehyst 0».
#   tests/levels/regpre_hyst.sh [EBOOT НАБОР]    без аргументов — только юнит
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
BIN="${TMPDIR:-/tmp}/regpre_unit.$$"; cc -O1 -o "$BIN" tests/levels/regpre_unit.c -lm || { echo "REGPRE-ГЕЙТ: FAIL (юнит не собрался)"; exit 1; }
"$BIN"; u=$?; rm -f "$BIN"; [ $u = 0 ] || { echo "REGPRE-ГЕЙТ: FAIL (юнит)"; exit 1; }
[ $# -ge 2 ] || { echo "REGPRE-ГЕЙТ: PASS (только юнит)"; exit 0; }
EB=$1; PK=$2; T="$ROOT/build/gates/regpre/$(date +%H%M%S)"; mkdir -p "$T"
P="$T/pk"; cp -cR "$PK" "$P" 2>/dev/null || cp -R "$PK" "$P"; cp "$EB" "$P/EBOOT.PBP"; trap 'rm -rf "$P"' EXIT
( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$ROOT/tests/levels/regpre_walk.txt" SMOKE_MAXT=${MAXT:-200} tools/smoke.sh "$P" ) > "$T/walk.out" 2>&1
G="$ROOT/$(sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' "$T/walk.out" | tail -1)"
g=$(.venv/bin/python tests/levels/regpre_hyst.py "$G"); echo "движок: $g"
[ "$(head -1 "$G/summary.txt")" = OK ] && grep -q "^REGPRE " "$G/smoke.txt" && case "$g" in *PASS*) echo "REGPRE-ГЕЙТ: PASS"; exit 0;; esac
echo "REGPRE-ГЕЙТ: FAIL (движок)"; exit 1

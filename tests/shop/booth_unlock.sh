#!/bin/bash
# №682 гейт: будка на L1 после загрузки настоящих сохранений Роба (tests/shop/fixtures, копии psp-pull/20261016):
#   save03 (все награды L2–L7 взяты, level=1) -> закрытых 0 среди просмотренных; save00 (4 миссии L1) -> закрыты все машины других уровней и награды L1 (только своя L1).
#   КРАСНЫЙ: сборка с -DPHONE_UNLOCK_OLD=1 на save03 обязана показать закрытые (прежнее). Параметр: DIR с EBOOT и данными; красный — RED_EBOOT=путь к такой сборке
set -u; cd "$(dirname "$0")/../.."
SRC="${1:-build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
run() { rm -rf "$T/h"; L=$(SMOKE_HOME="$T/h" SMOKE_SAVEFILES="$PWD/tests/shop/fixtures/$2=save00.bin" SHIP_LEVELS="" SMOKE_SCN="$PWD/tests/shop/booth_load_scenario.txt" SMOKE_HEADLESS=1 tools/smoke.sh "$1" 2>&1); echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p'; }
cnt() { grep -E "^PHONEV (open|sel)" "$1/smoke.txt" 2>/dev/null | grep -c "owned=0"; }
tot() { grep -E "^PHONEV (open|sel)" "$1/smoke.txt" 2>/dev/null | wc -l | tr -d ' '; }
A=$(run "$SRC" save03_dev_allrewards.bin); B=$(run "$SRC" save00_l1_4missions.bin)
a0=$(cnt "$A"); at=$(tot "$A"); b0=$(cnt "$B"); bt=$(tot "$B")
echo "save03: закрытых $a0 из $at; save00: закрытых $b0 из $bt"
ok=1; [ "$at" -ge 9 ] && [ "$a0" = 0 ] && [ "$b0" -ge 7 ] || ok=0
if [ -n "${RED_EBOOT:-}" ]; then cp -R "$SRC" "$T/red" && cp "$RED_EBOOT" "$T/red/EBOOT.PBP"; R=$(run "$T/red" save03_dev_allrewards.bin); r0=$(cnt "$R"); echo "красный (PHONE_UNLOCK_OLD): закрытых $r0"; [ "$r0" -ge 5 ] || ok=0; fi
[ $ok = 1 ] && echo PASS || { echo FAIL; exit 1; }

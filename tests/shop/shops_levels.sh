#!/bin/bash
# Лавка продавцов на L2–L7: tests/shop/shops_levels.sh [DIR]  (DIR — EBOOT со служебной «flag sellergo» + данные, у уровней 2–7 папки l2..l7; по умолчанию build/stage_shops)
# зелёный: у каждого продавца уровня △ открывает лавку со своей машиной (tests/shop/shops_levels_check.py); красный контроль: сценарий без «flag sellergo» — Гомер остаётся там, где стоял, лавки нет
# Причина прежних «лавка не открывается»: лавка идёт за САМИМ продавцом (правка 288, он ходит по маршруту AddPurchaseCarNPCWaypoint), а не стоит на локаторе; тест ставил Гомера на локатор
set -u; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build/stage_shops}"; SCN="$ROOT/tests/shop/shops_levels_scenario.txt"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
grep -v '^flag sellergo' "$SCN" > "$T/red.txt"
run() { local log; log=$(SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_MAXT=800 SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 10; done
RR=$(run "$T/red.txt"); echo "красный прогон: ${RR#$ROOT/}"
if .venv/bin/python tests/shop/shops_levels_check.py "$RR" > "$T/red.out" 2>&1; then echo "FAIL: сценарий без sellergo прошёл — гейт слепой"; cat "$T/red.out"; exit 1; fi
echo "красный как надо: $(grep FAIL "$T/red.out" | head -1)"
while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 10; done
RG=$(run "$SCN"); echo "прогон: ${RG#$ROOT/}"; .venv/bin/python tests/shop/shops_levels_check.py "$RG"

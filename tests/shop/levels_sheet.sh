#!/bin/bash
# Будка и гардероб на L2, L4, L7: tests/shop/levels_sheet.sh [DIR]  (DIR — EBOOT + данные, у уровней 2–7 папки l2..l7; по умолчанию build/t428/stage3)
# зелёный: на каждом уровне своя будка и свой гардероб (tests/shop/levels_sheet_check.py); красный контроль: сценарий без «flag golevel 4» — L4 не загружается, гейт обязан упасть
# Не покрыто: экран покупки у продавца (лавка Гила и др.) на L2–L7: кадром не снят (ходьба к продавцу в смоуке не открыла лавку за 3 попытки), на L2–L7 проверены только данные
set -u; ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build/t428/stage3}"; SCN="$ROOT/tests/shop/levels_sheet_scenario.txt"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
grep -v '^flag golevel 4$' "$SCN" > "$T/red.txt"
run() { local log; log=$(SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_MAXT=700 SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 10; done
RR=$(run "$T/red.txt"); echo "красный прогон: ${RR#$ROOT/}"
if .venv/bin/python tests/shop/levels_sheet_check.py "$RR" > "$T/red.out" 2>&1; then echo "FAIL: сценарий без golevel 4 прошёл — гейт слепой"; cat "$T/red.out"; exit 1; fi
echo "красный как надо: $(grep FAIL "$T/red.out" | head -1)"
while [ "$(pgrep -x PPSSPPHeadless | wc -l)" -ge 5 ]; do sleep 10; done
RG=$(run "$SCN"); echo "прогон: ${RG#$ROOT/}"; .venv/bin/python tests/shop/levels_sheet_check.py "$RG"

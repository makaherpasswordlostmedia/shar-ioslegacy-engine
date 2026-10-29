#!/bin/bash
# Гардероб Гомера (правка Роба 107) в эмуляторе: Kwik-E-Mart, место PurchaseSkin, покупка трусов за 100 и переодевание туда-обратно.
#   tests/shop/wardrobe_emu.sh [DIR]              зелёный: строки WARDV/WARDROBE (open, sel, buy, wear) и снимки (tests/shop/wardrobe_check.py)
#   tests/shop/wardrobe_emu.sh --negative [DIR]   красный: тот же путь без «flag coinadd» (монет нет) — сверка обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN="$PWD/tests/shop/wardrobe_scenario.txt"
if [ -n "$NEG" ]; then grep -v '^flag coinadd' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SHIP_LEVELS="" SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
.venv/bin/python tests/shop/wardrobe_check.py "$R" "$NEG"

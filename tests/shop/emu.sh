#!/bin/bash
# Экран покупки у продавца (пункт 6) в эмуляторе: сцена подиума и страница PurchaseRewards.scr, покупка Plow King у Барни, Гил.
#   tests/shop/emu.sh [DIR]              зелёный: строки SHOPV в smoke.txt (открыт, свет, звёзды, покупка 200 -> 50, конец) и снимки
#                                        (сцена: шторы и зелёный подиум; после покупки — снова город)
#   tests/shop/emu.sh --negative [DIR]   красный: flag shopvoff (экрана нет, прежняя карточка) — сверка обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/shop/emu_scenario.txt
if [ -n "$NEG" ]; then awk '/^flag msn/ && !d { print; print "flag shopvoff"; d = 1; next } { print }' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SHIP_LEVELS="" SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
.venv/bin/python tests/shop/emu_check.py "$R" "$NEG"

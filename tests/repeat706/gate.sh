#!/bin/bash
# №706 гейт: зажатая стрелка листает списки (задержка 0,4 с, шаг 0,12 с). Безголовый эмулятор, по одному прогону на список.
#   tests/repeat706/gate.sh [--old] [EBOOT_DIR] [списки...]    зелёный: во всех списках зажатие 1,5 с даёт >= порога шагов
#   --old   красный контроль: файл repeat706old рядом с EBOOT (прежний повтор: только ▲/▼) — гейт обязан покраснеть на ◄ ► (пауза ▲/▼ остаётся зелёной)
#   EBOOT_DIR: папка с EBOOT.PBP и данными (по умолчанию build/); SHIP_LEVELS="2" нужен списку shop
set -u; cd "$(dirname "$0")/../.."
OLD=""; [ "${1:-}" = --old ] && { OLD=1; shift; }
SRC="${1:-build}"; shift 2>/dev/null; LISTS="${*:-booth wardrobe menu pause shop}"
fail=0
for n in $LISTS; do
  SL=""; [ "$n" = shop ] && SL="2"
  L=$(SMOKE_HEADLESS=1 SMOKE_MAXT=800 SHIP_LEVELS="$SL" SMOKE_FLAGS="${OLD:+repeat706old}" SMOKE_SCN="$PWD/tests/repeat706/$n.txt" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
  [ -n "$R" ] || { echo "FAIL $n: нет отчёта: $(echo "$L" | head -1)"; fail=1; continue; }
  python3 tests/repeat706/check.py "$n" "$R/smoke.txt" || { echo "  FAIL $n ($R)"; fail=1; }
done
if [ -n "$OLD" ]; then [ $fail = 1 ] && echo "красный контроль: гейт покраснел (так и должно быть)" || { echo "красный контроль НЕ покраснел: гейт ничего не проверяет"; exit 1; }; exit 0; fi
[ $fail = 0 ] && echo "PASS" || { echo "FAIL"; exit 1; }

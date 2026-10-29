#!/bin/bash
# Гейт правки Роба 60: подсказка Барта не стопорит облёт старта уровня (tests/ui/tutcalm_scenario.txt через tools/smoke.sh).
#   tests/ui/tutcalm_emu.sh [DIR]              зелёный: облёт m0sd доходит до конца (MSNCAM end), подсказка «ходьба» — после него
#   tests/ui/tutcalm_emu.sh --negative [DIR]   красный: flag tutnow (подсказка сразу, как до правки) — сверка обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/ui/tutcalm_scenario.txt
if [ -n "$NEG" ]; then sed 's/^flag msn$/flag msn\nflag tutnow/' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
.venv/bin/python - "$R/smoke.txt" "$NEG" <<'PY'
import sys
rows = open(sys.argv[1], errors='replace').read().splitlines(); neg = sys.argv[2] == '1'
st = next((i for i, l in enumerate(rows) if l.startswith('MSNCAM start')), None)
en = next((i for i, l in enumerate(rows) if l.startswith('MSNCAM end')), None)
tu = next((i for i, l in enumerate(rows) if l.startswith('TUTORIAL on ev=walk')), None)
fails = []
if st is None: fails.append('облёт не начался (нет MSNCAM start)')
if en is None: fails.append('облёт не дошёл до конца (нет MSNCAM end) — заморожен')
if tu is None: fails.append('подсказка «ходьба» не показалась')
if None not in (st, en, tu) and not (tu > en): fails.append('подсказка «ходьба» на экране раньше конца облёта — облёт стоит')
if neg: print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман)'); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0]); sys.exit(1)
print('OK: облёт старта доходит до конца, подсказка «ходьба» — после него')
PY

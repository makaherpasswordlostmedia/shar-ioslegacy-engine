#!/bin/bash
# Гейт Г5/П4 (1): цели утра ботов (tools/bots/targets.py -> targets-l1.tsv) считают карточки и осы как игра и паспорт уровня.
# Сначала красный: старый счёт по именам локаторов (--legacy: 6 карточек, 23 осы) обязан упасть; потом зелёный (7 и 20).
set -u; cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
$PY tools/bots/targets.py --legacy --out "$T/old.tsv" >/dev/null || { echo "FAIL: targets.py --legacy не отработал"; exit 1; }
if $PY tests/collect_targets/check.py "$T/old.tsv" >"$T/old.txt"; then cat "$T/old.txt"; echo "FAIL: красный контроль (старый счёт) прошёл — гейт не ловит"; exit 1; fi
echo "красный (старый счёт по именам локаторов):"; sed 's/^/  /' "$T/old.txt"
$PY tools/bots/targets.py --out "$T/new.tsv" >/dev/null || { echo "FAIL: targets.py не отработал"; exit 1; }
if ! $PY tests/collect_targets/check.py "$T/new.tsv" >"$T/new.txt"; then cat "$T/new.txt"; echo "FAIL: зелёный"; exit 1; fi
echo "зелёный (игровые объекты collect-l1.shr):"; sed 's/^/  /' "$T/new.txt"
echo "PASS collect_targets"

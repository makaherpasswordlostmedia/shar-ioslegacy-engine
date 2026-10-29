#!/bin/bash
# Гейт 904: ворота Бернса (L1 F9-1) с высоты 22 м — решётка с мипами до 2 уровней (новое) против полного набора (flag lattice 0, красный контроль).
# usage: tests/lattice/lattice_mips.sh EBOOT [RUN.sh] ; RUN.sh — безголовый раннер (аргументы: сценарий метка EBOOT секунд, образец run/run.sh)
set -e
D=$(cd "$(dirname "$0")" && pwd); EB=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); RUN=${2:-$D/../../run/run.sh}; T=$(mktemp -d)
sed 's/@LAT@/0/' "$D/gate22.txt" > "$T/old.txt"; sed 's/@LAT@/1/' "$D/gate22.txt" > "$T/new.txt"
O=$(cd "$(dirname "$RUN")" && pwd)
"$RUN" "$T/old.txt" LATO "$EB" 300 >/dev/null; "$RUN" "$T/new.txt" LATN "$EB" 300 >/dev/null
python3 "$D/lattice_mips.py" "$O/out_LATO/g22.png" "$O/out_LATN/g22.png" "$O/out_LATN/smoke.txt"

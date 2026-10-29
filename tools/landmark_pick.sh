#!/bin/bash
# №928: ориентиры дали уровней автоматически: 16 самых заметных высоких объектов каждого уровня (landmark_scan.py, превышение над окрестностью ≥ PROM м) -> tools/horizon_landmarks.json
#   tools/landmark_pick.sh НАБОР_КАТАЛОГ [PROM=30]    НАБОР — каталог PSP/GAME/SHARTEST15 (L1 — level.shr в корне, L2..L7 — l<N>/level.shr)
set -u; SET=$1; PROM=${2:-30}; ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PY=${PY:-$ROOT/.venv/bin/python}; T=$(mktemp -d)
for L in 1 2 3 4 5 6 7; do
  F=$SET/l$L/level.shr; [ $L = 1 ] && F=$SET/level.shr
  $PY $ROOT/tools/landmark_scan.py $F --prom $PROM --top 16 --json $T/l$L.json > /dev/null 2>&1 &
  if [ $((L % 3)) = 0 ]; then wait; fi
done; wait
python3 - "$T" "$ROOT/tools/horizon_landmarks.json" <<'PY'
import json, sys, os
T, out = sys.argv[1], sys.argv[2]; d = {}
for L in range(1, 8):
    p = f'{T}/l{L}.json'
    if os.path.exists(p): d[str(L)] = [[o['x'], o['z'], o['r']] for o in json.load(open(p))]
json.dump(d, open(out, 'w'), ensure_ascii=False, indent=1); print({k: len(v) for k, v in d.items()})
PY
rm -rf $T

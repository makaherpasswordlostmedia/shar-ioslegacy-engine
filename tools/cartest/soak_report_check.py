#!/usr/bin/env python3
"""Гейт пункта 5: известный подтверждённый повтором случай (build/sandbox/replay-check.json: seed 101, машина 6,
тик 1569, проникновение) попадает в кластер проникновений сводки кампании (клетка 8 м или соседняя).
Отрицательный контроль встроен: далёкая точка и та же сводка с вычеркнутыми клетками случая обязаны НЕ попасть.
  python3 tools/cartest/soak_report_check.py [--report build/sandbox/soak-report.json]
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def in_cluster(cells, cols, x, z, kind='penetration', cell=8.0):
    k = cols.index(kind)
    cx, cz = math.floor(x / cell), math.floor(z / cell)
    near = {(c[0], c[1]): c[k] for c in cells if abs(c[0] - cx) <= 1 and abs(c[1] - cz) <= 1}
    return sum(near.values()), sorted(near.items(), key=lambda kv: -kv[1])[:3]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--report', type=Path, default=ROOT / 'build/sandbox/soak-report.json')
    a = ap.parse_args()
    rep = json.loads(a.report.read_text()); cells, cols = rep['allCells'], rep['allCellsColumns']
    case = json.loads((ROOT / 'build/sandbox/replay-check.json').read_text())
    ev = case['events'][0]; x, _, z = ev['xyz']
    n, near = in_cluster(cells, cols, x, z)
    far, _ = in_cluster(cells, cols, 5000.0, 5000.0)
    # та же сводка без клеток случая: проба обязана покраснеть
    cx, cz = math.floor(x / 8), math.floor(z / 8)
    cut = [c for c in cells if not (abs(c[0] - cx) <= 1 and abs(c[1] - cz) <= 1)]
    ncut, _ = in_cluster(cut, cols, x, z)
    replayed = [t for t in rep['top'] if t.get('class', {}).get('replayed')]
    print('случай seed %s машина %d тик %d (%.1f, %.1f): проникновений в клетке и соседних %d %s' % (
        case['command'][-1], ev['car'], ev['tick'], x, z, n, near))
    print('контроль: далёкая точка %d, сводка без клеток случая %d' % (far, ncut))
    print('повторы топа совпали с событием: %d из %d' % (len(replayed), len(rep['top'])))
    ok = n > 0 and far == 0 and ncut == 0
    print('soak_report_check: ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())

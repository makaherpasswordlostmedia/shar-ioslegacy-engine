#!/usr/bin/env python3
"""Гейт пункта 9: в build/sandbox/routes-l1.json у всех 16 jumpzone (jumps.p3d) и у всех 13 стёкол Krusty (PRP2, обломок
19) есть запись с кромкой, подъездом и приземлениями; ожидаемые числа берутся из данных, не из головы.
Отрицательный контроль встроен: тот же файл без одной зоны и без одного стекла обязан покраснеть."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/cartest'))
import routes as R  # noqa: E402

def verdict(rep, zones, glass):
    names = {r['name'] for r in rep['ramps'] if 'lip' in r and len(r.get('landing', {})) == len(R.SPEEDS)}
    have_g = {r['glass'] for r in rep['ramps'] if r.get('glass') is not None and 'lip' in r}
    miss_z = sorted(z for z in zones if z not in names); miss_g = sorted(g for g in glass if g not in have_g)
    return miss_z, miss_g

rep = json.loads((ROOT / 'build/sandbox/routes-l1.json').read_text())
zones = [z['name'] for z in R.locators(R.G / 'art/missions/level01/jumps.p3d', lambda n, k, e: e == 48)]
glass = [g['inst'] for g in R.glass_panes(ROOT / rep['level'])]
mz, mg = verdict(rep, zones, glass)
print('в данных: зон %d, стёкол %d; без записи: зоны %s, стёкла %s' % (len(zones), len(glass), mz or '—', mg or '—'))
cut = dict(rep, ramps=[r for r in rep['ramps'] if r['name'] != zones[0] and r.get('glass') != glass[-1]])
cz, cg = verdict(cut, zones, glass)
print('контроль: без %s и без стекла #%d → не найдено зон %d, стёкол %d' % (zones[0], glass[-1], len(cz), len(cg)))
ok = len(zones) == 16 and len(glass) == 13 and not mz and not mg and cz and cg
print('routes_check: ' + ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)

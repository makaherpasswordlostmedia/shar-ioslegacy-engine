#!/usr/bin/env python3
"""Находки нативных ботов Мака (дорожка night_native.sh) в TSV формата autoexplore: level, x, y, z, type, weight, seed, frame, description.
  python3 tools/night/native_findings.py ПАПКА_КРУГА SEED   -> строки в stdout (night_native.sh дописывает их в NIGHT_DIR/native/findings.tsv)
Источники в папке круга: missions/missions.json (миссионер: всё, что не «пройдена»), chase/chase.json (кластеры eternal_corner / pursuer_stuck),
explore/explore.json (не достигнутые цели), nav/nav.json (клетки потерь маршрутов). Нативные боты — L1 (roads-l1), уровень в строке всегда 1."""
import json, math, sys
from pathlib import Path
O = Path(sys.argv[1]); SEED = sys.argv[2] if len(sys.argv) > 2 else '0'
TG = Path.home() / 'Downloads/shar-psp/build/bots/targets-l1.tsv'


def row(x, y, z, typ, w, frame, desc):
    print('\t'.join(['1', '%.1f' % x, '%.1f' % y, '%.1f' % z, typ, str(max(1, min(10, int(w)))), SEED, str(frame), desc.replace('\t', ' ').replace('\n', ' ')]))


def load(p):
    try: return json.loads(p.read_text())
    except Exception: return None


m = load(O / 'missions/missions.json')
for r in m or []:
    if r['result'] == 'пройдена': continue
    typ = {'провал': 'mission_failed', 'застрял': 'mission_stuck'}.get(r['result'], 'mission_not_covered')
    w = 8 if r['result'] == 'застрял' and r.get('cls') in ('игра', '') else (5 if r['result'] == 'застрял' else 3)
    row(r['place'][0], 0.0, r['place'][1], typ, w, r.get('frames', 0), '%s %s: %s; класс %s; %.0f с, стадий %s' % (r['id'], r['title'], r['why'] or r['result'], r.get('cls') or '-', r['time'], r['stages']))
c = load(O / 'chase/chase.json')
for k in (c or {}).get('clusters', []):
    row(k['x'], k['y'], k['z'], k['kind'], 3 + math.log2(max(1, k['n'])), 0, 'догонялки: объект %s слой %s, раз %s, повтор %s' % (k.get('obj'), k.get('layer'), k['n'], k.get('replay')))
e = load(O / 'explore/explore.json')
pos = {}
try:
    for ln in TG.read_text().splitlines():
        f = ln.split('\t'); x, y, z = map(float, f[2].split()); pos[f[1]] = (x, y, z)
except Exception: pass
for name in (e or {}).get('unreached', []):
    x, y, z = pos.get(name, (0.0, 0.0, 0.0)); row(x, y, z, 'target_unreached', 4, 0, 'каскадёр/пешеход не достиг цели %s' % name)
n = load(O / 'nav/nav.json')
for k in (n or {}).get('lossCells', []):
    row(k['x'], 0.0, k['z'], 'nav_loss', 2 + math.log2(max(1, k['n'])), 0, 'навигатор: потери маршрутов в клетке 8 м, раз %s' % k['n'])

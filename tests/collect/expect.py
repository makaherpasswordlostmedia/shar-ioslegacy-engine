#!/usr/bin/env python3
"""Ожидания гейта В5 (tests/collect/host.sh) прямо из данных диска, НЕЗАВИСИМО от tools/collect_export.py: локаторы —
tools/missions/p3dlocs.py (свой разбор 0x3000005/0x3000006), скрипты — tools/missions/mfk.py. Пишет TSV:
  card  id  x y z r                               (ActionEvent CollectorCard: номер из данных локатора)
  wasp  name  x y z dist                          (AddSpawnPointByLocatorScript beecamera + локатор wasps.p3d)
  gag   file  room  trig(0 touch/1 action)  cycle(0 single/1 cycle/2 reset)  random  coins  x y z r  fmv
Координаты движка (z отзеркален). python3 tests/collect/expect.py > build/collect/expect.tsv"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from missions.p3dlocs import read_locators
import missions.mfk as M
G = (ROOT / 'hit-and-run-web/source/game').resolve()
LV = int(sys.argv[1]) if len(sys.argv) > 1 else 1
ROOM = {'springfieldelementary': 0, 'kwikemart': 1, 'simpsonshouse': 2, 'dmv': 3, 'moes': 4,
        'androidsdungeon': 5, 'android': 5, 'moe1': 4, 'observatory': 6, 'bartroom': 7}
art = G / 'art'
files = [art / f'l{LV}_terra.p3d', *sorted(art.glob(f'l{LV}[rzi]*.p3d')), *sorted((art / f'missions/level0{LV}').glob('*.p3d'))]
locs = {}
for f in files:
    L, err = read_locators(f, f.name)
    for l in L: locs.setdefault(l.name, l)
    # карточки: данные локатора (строки) — сами из сырых байт, p3dlocs хранит только тип
    for l in L:
        if l.type != 9: continue
out = []
from p3d import read, walk, string   # noqa: E402 (путь hit-and-run-web/tools добавил p3dlocs)
import struct
for f in files:
    for c in walk(read(f)):
        if c.id != 0x3000005: continue
        name, p = string(c.data); kind, n = struct.unpack_from('<II', c.data, p)
        strs = [s.decode('latin1') for s in c.data[p + 8:p + 8 + 4 * n].split(b'\0') if s]
        if kind == 9 and 'CollectorCard' in strs:
            l = next(x for x in read_locators(f, f.name)[0] if x.name == name and x.type == 9)
            r = max(l.triggers[0][2]) if l.triggers else 1.0
            out.append(('card', re.sub(r'\D', '', strs[0]), *l.pos, r))
calls, _ = M.parse((G / f'scripts/missions/level0{LV}/leveli.mfk').read_text(errors='replace'))
for c in calls:
    if c.op == 'AddSpawnPointByLocatorScript' and str(c.args[1]).lower() == 'beecamera':
        l = locs[str(c.args[3])]
        out.append(('wasp', str(c.args[0]), *l.pos, float(c.args[5])))
calls, _ = M.parse((G / f'scripts/missions/level0{LV}/level.mfk').read_text(errors='replace'))
g = None
for c in calls:
    a = c.args
    if c.op == 'GagBegin': g = dict(file=Path(str(a[0])).stem, room=-1, trig=0, cycle=0, random=0, coins=0, fmv='-', t=None)
    elif g is None: continue
    elif c.op == 'GagSetInterior': g['room'] = ROOM.get(str(a[0]).lower(), -1)
    elif c.op == 'GagSetCycle': g['cycle'] = {'single': 0, 'cycle': 1, 'reset': 2}[str(a[0]).lower()]
    elif c.op == 'GagSetRandom': g['random'] = int(a[0])
    elif c.op == 'GagSetCoins': g['coins'] = int(a[0])
    elif c.op == 'GagPlayFMV': g['fmv'] = Path(str(a[0])).stem
    elif c.op == 'GagSetTrigger':
        g['trig'] = 1 if str(a[0]).lower() == 'action' else 0
        if len(a) == 3: l = locs[str(a[1])]; g['t'] = (*l.pos, float(a[2]))
        else: g['t'] = (float(a[1]), float(a[2]), -float(a[3]), float(a[4]))
    elif c.op == 'GagEnd':
        out.append(('gag', g['file'], g['room'], g['trig'], g['cycle'], g['random'], g['coins'], *(g['t'] or (0., 0., 0., 0.)), g['fmv'])); g = None
# Coins and wrench spheres from city scenes only; interior/mission props are separate systems.
for f in [art / f'l{LV}_terra.p3d', *sorted(art.glob(f'l{LV}r*.p3d')), *sorted(art.glob(f'l{LV}z*.p3d'))]:
    ls, err = read_locators(f, f.name)
    if err: raise RuntimeError(err)
    for l in ls:
        if l.type == 14: out.append(('coin', l.name, *l.pos, 0.))
    for c in walk(read(f)):
        if c.id != 0x3000005: continue
        name, p = string(c.data); kind, n = struct.unpack_from('<II', c.data, p)
        strs = [v.decode('latin1') for v in c.data[p+8:p+8+4*n].split(b'\0') if v and all(32 <= b < 127 for b in v)]
        if kind != 9 or not strs or strs[-1] != 'Wrench': continue
        l = next(v for v in ls if v.name == name and v.type == 9)
        if not l.triggers: raise RuntimeError(f'wrench without sphere: {name}')
        shape, pos, half, axes = l.triggers[0]
        out.append(('wrench', name, *pos, half[0]))
for r in out: print('\t'.join(f'{v:.4f}' if isinstance(v, float) else str(v) for v in r))

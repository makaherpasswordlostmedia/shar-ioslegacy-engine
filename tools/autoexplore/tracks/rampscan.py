#!/usr/bin/env python3
"""Все трамплины (зоны прыжка JMP1) уровня: заезд настоящей машиной хоста (rampsim.c: тот же col.c и car.c, что в игре) с четырёх сторон по осям зоны,
по нескольким полосам и скоростям 36/54/72/90 км/ч. Итог по зоне и стороне: сколько заездов дошли до зоны не потеряв скорость, какие примитивы остановили остальные.
  python3 rampscan.py LEVEL.shr [--out DIR] [--speeds 36,54,72,90]   → таблица в stdout; --tsv FILE дописывает находки (ramp_blocked) в формате INTERFACE.md"""
import argparse, math, subprocess, sys, tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
import os
SRC = Path(os.environ.get('GAME_VIEWER') or HERE.parents[2] / 'viewer')   # исходники игры (col.c, car.c): по умолчанию из этого рабочего дерева; GAME_VIEWER=каталог viewer нужной сборки
def build():
    out = {}
    for name, extra in (('rampsim', ['-DCOL_DEBUG', str(SRC / 'car.c')]), ('coljumps', [])):
        tag = os.environ.get('AE_TAG', ''); exe = Path('/tmp') / f'ae_{name}{tag}'; src = HERE / f'{name}.c'
        if not exe.exists() or exe.stat().st_mtime < max(src.stat().st_mtime, (SRC / 'col.c').stat().st_mtime, (SRC / 'car.c').stat().st_mtime):
            subprocess.check_call(['cc', '-std=c99', '-O2', '-I', str(SRC), str(src), str(SRC / 'col.c')] + extra + os.environ.get('AE_CFLAGS', '').split() + ['-lm', '-o', str(exe)])
        out[name] = str(exe)
    return out
def zones(exe, level_shr):
    res = []
    for l in subprocess.run([exe, level_shr], capture_output=True, text=True).stdout.splitlines():
        p = l.split()
        if p[0] != 'zone': continue
        v = [float(x) for x in p[6:] if x not in ('h', 'ax', 'ay', 'az', 'c')]
        res.append(dict(name=p[2], shape=int(p[4]), c=v[0:3], h=v[3:6], ax=v[6:9], ay=v[9:12], az=v[12:15]))
    return res
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('--speeds', default='36,54,72,90'); ap.add_argument('--back', type=float, default=40.0); ap.add_argument('--tsv'); ap.add_argument('--level-no', type=int, default=0)
    a = ap.parse_args(); exe = build(); Z = zones(exe['coljumps'], a.level); speeds = [float(s) for s in a.speeds.split(',')]
    cases = []; meta = {}
    for zi, z in enumerate(Z):
        if z['shape'] != 1: continue
        c = np.array(z['c']); axs = [np.array(z['ax']), np.array(z['az'])]; hs = [z['h'][0], z['h'][2]]
        for di, (sgn, ai) in enumerate([(1, 0), (-1, 0), (1, 1), (-1, 1)]):
            d = axs[ai] * sgn; d[1] = 0; n = np.linalg.norm(d)
            if n < 1e-6: continue
            d /= n; perp = np.array([-d[2], 0, d[0]]); hw = hs[1 - ai]; lanes = sorted(set([0.0] + [round(o, 1) for o in np.arange(-min(hw * .75, 6), min(hw * .75, 6) + .01, 2.5)]))
            for off in lanes:
                p = c - d * a.back + perp * off; h = math.atan2(d[0], d[2])
                for kmh in speeds:
                    tag = f'{zi}_{di}_{off:+.1f}_{int(kmh)}'; meta[tag] = (zi, di, off, kmh)
                    cases.append(f'{tag} {p[0]:.2f} {c[1] - 2.0:.2f} {p[2]:.2f} {h:.4f} {kmh} {c[0]:.2f} {c[2]:.2f} 9')
    out = subprocess.run([exe['rampsim'], a.level], input='\n'.join(cases) + '\n', capture_output=True, text=True).stdout.splitlines()
    agg = defaultdict(lambda: dict(pass_=0, fail=0, skip=0, hits=defaultdict(int), first=None, minv=99))
    for l in out:
        p = l.split(); tag = p[0]; zi, di, off, kmh = meta[tag]; g = agg[(zi, di)]
        if p[1] == 'SKIP': g['skip'] += 1; continue
        if p[1].startswith('PASS') and p[1] == 'PASS': g['pass_'] += 1; continue
        g['fail'] += 1
        if 'hit' in p:
            i = p.index('hit'); pr = p[p.index('prims') + 1] if 'prims' in p else ''
            if p[i - 1] and 'prims' in p: g['hits'][pr or '?'] += 1
            if g['first'] is None: g['first'] = (kmh, off, p[i + 1], ' '.join(p[i + 3:i + 6]))
    print(f'{"зона":<14}{"сторона":<8}{"дошли":>6}{"не дошли":>9}{"недоступно":>11}  кто останавливает (тип:номер = заездов)')
    rows = []
    for (zi, di), g in sorted(agg.items()):
        z = Z[zi]; tot = g['pass_'] + g['fail']
        if tot == 0: continue
        who = ', '.join(f'{k}={v}' for k, v in sorted(g['hits'].items(), key=lambda kv: -kv[1])[:3])
        print(f'{z["name"]:<14}{["+x", "-x", "+z", "-z"][di]:<8}{g["pass_"]:>6}{g["fail"]:>9}{g["skip"]:>11}  {who}'); rows.append((zi, di, g, tot))
        if a.tsv and g['fail'] and g['fail'] * 2 > tot:
            c = z['c']; w = int(min(10, 3 + 7 * g['fail'] / tot))
            with open(a.tsv, 'a') as o: o.write('\t'.join([str(a.level_no), '%.1f' % c[0], '%.1f' % c[1], '%.1f' % c[2], 'ramp_blocked', str(w), '0', '0', f'{z["name"]} сторона {["+x", "-x", "+z", "-z"][di]}: не дошли {g["fail"]} из {tot} заездов 36–90 км/ч; останавливают {who}']) + '\n')
if __name__ == '__main__': main()

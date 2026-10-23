#!/usr/bin/env python3
"""Ночные боты (№876, Роб 23.10): сценарии безголового эмулятора на текущем наборе TEST.
  python3 tools/night/make_scenarios.py OUTDIR [--points 100]
Пишет OUTDIR/explore_L{N}.txt (фото-исследователь: точки бота-репортёра build/scout/l{N}.bin, 4 направления камеры, журнал выброса GE),
OUTDIR/gags_L{N}.txt (гэги с персонажами: gaglist, затем каждый гэг дважды gagplay — вход в комнату, потом игра, 2 снимка),
OUTDIR/soak.txt (долгая игра: круг L1→L7, на каждом уровне езда; память — строки LEVEL ev=load/STAT)."""
import struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
NP = int(sys.argv[sys.argv.index('--points') + 1]) if '--points' in sys.argv else 100
GAGS = {1: 33, 2: 30, 3: 30, 4: 33, 5: 30, 6: 30, 7: 33}   # верхняя граница числа гэгов (лишние индексы движок игнорирует)

def points(L, n):
    b = (ROOT / f'build/scout/l{L}.bin').read_bytes(); nt, npc, npt = struct.unpack_from('<III', b, 4)
    off = 16 + nt * 36 + nt * 4 + npc * 28; P = np.frombuffer(b, '<f4', npt * 3, off).reshape(-1, 3)
    if len(P) <= n: return P
    sel = [0]; d = np.linalg.norm(P[:, [0, 2]] - P[0, [0, 2]], axis=1)   # самые удалённые друг от друга
    for _ in range(n - 1):
        i = int(np.argmax(d)); sel.append(i); d = np.minimum(d, np.linalg.norm(P[:, [0, 2]] - P[i, [0, 2]], axis=1))
    return P[sel]

head = lambda L: ['wait 12'] + ([] if L == 1 else ['scene LOAD', f'flag golevel {L}', 'wait 40']) + ['flag cfgdefaults 1', 'flag diaglog 1']
for L in range(1, 8):
    s = head(L) + ['flag camin 1']
    for i, p in enumerate(points(L, NP)):
        s += [f'scene P{i:03d}', f'foot {p[0]:.1f} {p[2]:.1f} 0', 'wait 1.6']
        for k in range(4): s += ['shot e%03d_%d' % (i, k), 'press r 1.0', 'wait 1.15']
    (out / f'explore_L{L}.txt').write_text('\n'.join(s + ['end']) + '\n')
    g = head(L) + ['flag gaglist 1', 'wait 0.5']
    for k in range(GAGS[L]):
        g += [f'scene G{k:02d}', f'flag gagplay {k}', 'wait 1.5', f'flag gagplay {k}', 'wait 1.0', f'shot g{k:02d}_a', 'wait 1.5', f'shot g{k:02d}_b']
    (out / f'gags_L{L}.txt').write_text('\n'.join(g + ['end']) + '\n')
s = ['wait 12', 'flag cfgdefaults 1']
for rnd in range(5):
    for L in range(1, 8):
        s += [f'scene R{rnd}_L{L}', f'flag golevel {L}', 'wait 40', 'press triangle 0.2', 'wait 3', 'flag drive 20', 'wait 120', 'flag stop', 'press triangle 0.2', 'wait 4']
(out / 'soak.txt').write_text('\n'.join(s + ['end']) + '\n')
print('сценарии:', sorted(p.name for p in out.glob('*.txt')))

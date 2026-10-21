#!/usr/bin/env python3
"""Гейт К4 (полосы): кадр «полосы» = кадр «список» на точках уровней L1–L7 (допуск: доля пикселей с разницей > 8 по каналу ≤ 0,5 %), красный контроль.
  python3 tools/strips_gate.py make-scn LEVELS_DIR OUT.txt [--points N] [--levels 1 2 ...]   сценарий смоука: golevel, точки goto+shot (по высотной карте level.shr)
  python3 tools/strips_gate.py cmp DIR_A DIR_B [--limit 0.5]   сравнить png снимков двух прогонов (build/smoke/<время>/), вердикт и таблица
LEVELS_DIR — набор игры (SHARTEST15): L1 level.shr в корне, L2–L7 в l2…l7/level.shr."""
import argparse, struct, sys
from pathlib import Path
def points(path, n):
    d = open(path, 'rb').read(200 + 104); hd = struct.unpack_from('<14f', d, 12); hox, hoz, hc = hd[11], hd[12], hd[13]; W, H = struct.unpack_from('<2i', d, 68)
    import mmap
    f = open(path, 'rb'); m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ); st = max(1, int(50 / hc)); pts = []; row = 0
    for gz in range(st // 2, H, st):
        for j in range(W // st + 1):
            gx = st // 2 + ((W // st - j) if row & 1 else j) * st
            if gx < 0 or gx >= W: continue
            c = struct.unpack_from('<4h', m, 104 + (gz * W + gx) * 8)
            ok = [v for v in c if v != -32768]
            if not ok or min(ok) < -3000: continue
            pts.append((hox + (gx + .5) * hc, hoz + (gz + .5) * hc))
        row += 1
    sp = (hd[6], hd[8], hd[9]) if False else None
    step = max(1, len(pts) // n); return pts[::step][:n], (hd[6], hd[7], hd[8], hd[9])
def make(a):
    base = Path(a.levels_dir); out = ['# гейт полос: точки по высотной карте level.shr, сценарий общий для обоих прогонов']
    for lv in a.levels:
        lvl = base / ('level.shr' if lv == 1 else f'l{lv}/level.shr'); pts, sp = points(lvl, a.points)
        out += [f'scene L{lv}', 'flag newsshot 0']
        if lv != 1: out += [f'flag golevel {lv}', 'wait 22']
        else: out += ['wait 4']
        if a.pair or a.rf: out += ['flag dloff 1']   # город по кускам: переключатель stripslist действует сразу
        for i, (x, z) in enumerate(pts):
            h = (0.0, 1.5708, 3.1416, 4.7124)[i % 4]
            if a.rf: out += [f'scene L{lv}_{i:02d}', f'goto {x:.1f} {z:.1f} {h:.4f}', 'wait 2.5', f'flag stripscompare {2 if a.red else 1}', 'wait 1.5']
            elif a.pair: out += [f'goto {x:.1f} {z:.1f} {h:.4f}', 'wait 2.5', 'flag stripslist 0', 'wait 0.3', f'shot L{lv}_{i:02d}_s', f'flag stripslist {2 if a.red else 1}', 'wait 0.3', f'shot L{lv}_{i:02d}_l', 'flag stripslist 0']
            else: out += [f'goto {x:.1f} {z:.1f} {h:.4f}', 'wait 2.5', f'shot L{lv}_{i:02d}']
    out += ['end']; Path(a.out).write_text('\n'.join(out) + '\n'); print(a.out, len(out), 'строк')
def pair(a):
    from PIL import Image
    import numpy as np
    D = Path(a.dir); bad = 0; tot = 0; worst = 0.0
    for p in sorted(D.glob('*_s.png')):
        q = p.with_name(p.name[:-6] + '_l.png')
        if not q.exists(): continue
        x = np.asarray(Image.open(p).convert('RGB'), dtype=np.int16); y = np.asarray(Image.open(q).convert('RGB'), dtype=np.int16)
        pc = 100.0 * float((np.abs(x - y).max(axis=2) > 8).mean()); tot += 1; worst = max(worst, pc); bad += pc > a.limit
        print(f'{p.name[:-6]:10} {pc:8.3f}' + ('  <-- выше допуска' if pc > a.limit else ''))
    print(f'пар {tot}, выше допуска {bad}, худший {worst:.3f} % (допуск {a.limit} %)'); sys.exit(1 if bad or not tot else 0)
def rfcmp(a):
    from PIL import Image
    import numpy as np
    D = Path(a.dir); bad = 0; tot = 0; worst = 0.0
    def px(f): return np.asarray(Image.open(f).convert('RGB'), dtype=np.int16)
    for p0 in sorted(D.glob('rf_*_0.png')):
        base = p0.name[:-6]; ps = [D / f'{base}_{k}.png' for k in range(5)]
        if not all(q.exists() for q in ps): print(base, 'нет всех пяти проходов'); bad += 1; continue
        im = [px(q) for q in ps]; worstp = 0.0
        for i, j in ((0, 1), (2, 3), (0, 2), (0, 4), (1, 3)):   # полосы/список, и согласие одноимённых проходов
            worstp = max(worstp, 100.0 * float((np.abs(im[i] - im[j]).max(axis=2) > 8).mean()))
        tot += 1; worst = max(worst, worstp); bad += worstp > a.limit
        print(f'{base[3:]:10} {worstp:8.3f}' + ('  <-- выше допуска' if worstp > a.limit else ''))
    print(f'точек {tot}, выше допуска {bad}, худший {worst:.3f} % (допуск {a.limit} %)'); sys.exit(1 if bad or not tot else 0)
def cmp(a):
    from PIL import Image
    import numpy as np
    A = {p.stem: p for p in Path(a.dir_a).glob('*.png') if not p.name.startswith('contact')}; B = {p.stem: p for p in Path(a.dir_b).glob('*.png') if not p.name.startswith('contact')}
    names = sorted(set(A) & set(B)); bad = 0; worst = 0.0; tot = 0
    Z = {p.stem: p for p in Path(a.base).glob('*.png')} if a.base else {}   # второй прогон эталона: шум движущегося (облака, значки, люди) — допуск снимка не меньше шума + 0,2 %
    print(f'{"снимок":14} {"разных пикс. %":>14}')
    for n in names:
        x = np.asarray(Image.open(A[n]).convert('RGB'), dtype=np.int16); y = np.asarray(Image.open(B[n]).convert('RGB'), dtype=np.int16)
        if x.shape != y.shape: print(n, 'размеры разные'); bad += 1; continue
        pc = 100.0 * float((np.abs(x - y).max(axis=2) > 8).mean()); tot += 1; lim = a.limit
        if n in Z: z = np.asarray(Image.open(Z[n]).convert('RGB'), dtype=np.int16); noise = 100.0 * float((np.abs(x - z).max(axis=2) > 8).mean()); lim = max(lim, noise + 0.2)
        else: noise = -1.0
        worst = max(worst, pc)
        if pc > lim: bad += 1
        print(f'{n:14} {pc:14.3f}  шум эталона {noise:6.3f}' + ('  <-- выше допуска' if pc > lim else ''))
    miss = (set(A) ^ set(B))
    print(f'снимков сопоставлено {tot}, без пары {len(miss)}, выше допуска {bad}, худший {worst:.3f} % (допуск {a.limit} %)')
    sys.exit(1 if bad or not tot else 0)
ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
m = sub.add_parser('make-scn'); m.add_argument('levels_dir'); m.add_argument('out'); m.add_argument('--points', type=int, default=8); m.add_argument('--levels', type=int, nargs='+', default=[1, 2, 3, 4, 5, 6, 7]); m.add_argument('--pair', action='store_true'); m.add_argument('--rf', action='store_true'); m.add_argument('--red', action='store_true')
c = sub.add_parser('cmp'); c.add_argument('dir_a'); c.add_argument('dir_b'); c.add_argument('--limit', type=float, default=0.5); c.add_argument('--base', default='')
rr = sub.add_parser('rfcmp'); rr.add_argument('dir'); rr.add_argument('--limit', type=float, default=0.5)
pp = sub.add_parser('pair'); pp.add_argument('dir'); pp.add_argument('--limit', type=float, default=0.5)
a = ap.parse_args(); make(a) if a.cmd == 'make-scn' else rfcmp(a) if a.cmd == 'rfcmp' else pair(a) if a.cmd == 'pair' else cmp(a)

#!/usr/bin/env python3
"""№916б: рывок глаза камеры пешком. По сцене --scene (YARD — заход во двор Симпсонов L1 x 215, z 193 -> 186; WK_L1 — автопилот ходьбы 30 с, L1):
глаз не смещается относительно опоры больше LIM м за кадр (CAMIN jmax; строки CAMJUMP при flag camlog — справочно) и ничего не режется у края кадра
(CAMIN near/ground/car/person = 0). Красный контроль: YARD + flag camcrossold 1, PK_L1 + flag camsoftpplold 1, FLIP_L1 (--lim 0.3) + flag camflip1old 1 -> FAIL (WK_L6 красного не имеет: автопилот L6 на test67+ не упирается в стену с перескоком).
PK_L1 (перелёт глаза мимо человека: flag camkick сдвигает прошлый глаз, flag pedbehind ставит человека на его линию): ни одного рывка > LIM м за кадр (строки CAMJUMP flag camlog).
WK_L6 (перескок камеры у стены по записи PS2 — один резкий кадр по замыслу): --cuts 1 — рывков глаза > LIM м (строки CAMJUMP flag caminlog) не больше одного.
CARW_L1 (№982: за спиной Гомера стоит автобус, Гомер идёт от него; --noflip — ни одного перескока камеры через героя; прежний код flag camcar982old 1 перескакивает: CAMFLIP 1)
python3 eyejump.py smoke.txt --scene YARD|PK_L1|WK_L1|WK_L4|WK_L6|WK_L7|FLIP_L1|CARW_L1 [--lim 1.5] [--cuts N] [--noflip] [--expect fail]"""
import re, sys
a = sys.argv[1:]; LIM = float(a[a.index('--lim') + 1]) if '--lim' in a else 1.5
scene = a[a.index('--scene') + 1] if '--scene' in a else 'YARD'
cuts = int(a[a.index('--cuts') + 1]) if '--cuts' in a else None
noflip = '--noflip' in a
exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
sc = None; jumps = []; camin = None; flips = 0
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); continue
    if sc != scene: continue
    if l.startswith('CAMFLIP'): flips += 1
    m = re.search(r'CAMJUMP t=(\S+) (?:d|j)=(\S+)', l)
    if m: jumps.append((float(m.group(1)), float(m.group(2))))
    m = re.match(r'CAMIN .*? frames=(\d+) any=(\d+) eye=(\d+) near=(\d+) ground=(\d+) car=(\d+) person=(\d+) occ=(\d+).*? jump=(\d+) jmax=(\S+)', l)
    if m and int(m.group(1)) > (30 if scene == 'PK_L1' else 100):
        camin = dict(zip(('frames', 'any', 'eye', 'near', 'ground', 'car', 'person', 'occ', 'jump', 'jmax'), map(float, m.groups())))
if not camin:
    print(scene + ': нет строки CAMIN (сцена не дошла до конца)'); print('FAIL'); sys.exit(0 if exp_fail else 1)
big = [j for j in jumps if j[1] > LIM]
if cuts is not None: print(f'{scene}: перескоков камеры (рывков глаза > {LIM} м за кадр): {len(big)} (допустимо {cuts}), наибольший {camin["jmax"]:.2f} м')
print(f'{scene}: кадров {camin["frames"]:.0f}, рывков глаза > 0,5 м: {camin["jump"]:.0f}, наибольший {camin["jmax"]:.2f} м за кадр (предел {LIM}); CAMJUMP > {LIM} м: {len(big)}')
print(f'  внутри: eye={camin["eye"]:.0f} near={camin["near"]:.0f} ground={camin["ground"]:.0f} car={camin["car"]:.0f} person={camin["person"]:.0f}; человек/кузов между опорой и глазом (справочно) occ={camin["occ"]:.0f}')
if noflip: print(f'{scene}: перескоков камеры через героя (CAMFLIP): {flips}, допустимо 0')
ok = (not noflip or flips == 0) and (len(big) <= cuts if cuts is not None else camin['jmax'] <= LIM and not big) and camin['near'] == 0 and camin['ground'] == 0 and camin['car'] == 0 and camin['person'] == 0
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok != exp_fail else 1)

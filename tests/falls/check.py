#!/usr/bin/env python3
"""Гейт Г4 (L1_ФИНИШ) / правка Роба 142: провалы Гомера под мир — ночь ботов 30.09→01.10, топ-20 мест и довески 65/95/143.
Повторы tests/bots/regress/g4_*.in (свой ввод каскадёра, не ресурс игры) проигрываются game_headless тремя сборками мира:
  зелёная  — как есть: правило «край без дна — стена» (viewer/homer.c, HOMER_VOID_WALL) и зона DEATH в мире ботов (game.c gameDeath);
  красная1 — -DHOMER_VOID_WALL=0: Гомер уходит за край без опоры (как до 01.10);
  красная2 — BW_NO_DEATH=1: в мире ботов нет возврата зоной DEATH (как до 01.10: канал под мостом l1r7 считался провалом).
Провал = игрок ниже FALL_Y (м) хоть на одном кадре повтора. Закон 4: соседние варианты того же ввода (стик повёрнут на ±10°/±20°,
×0.7, бег ↔ шаг) — в зелёной провалов нет ни одного, в старой (обе красные разом) они есть (варианты действительно доходят до краёв).
Положительные контроли: в зелёной Гомер по-прежнему спрыгивает с уступов (падение ≥ 2 м с приземлением есть), а прыжок с моста l1r7
в канал доходит до зоны DEATH и возвращается ею (перенос > 5 м за кадр) — правило не запирает законные падения.
  python3 tests/falls/check.py BIN_GREEN BIN_RED_VOID   -> PASS / FAIL"""
import math, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LVL, HOM = ROOT / 'build/level.shr', ROOT / 'build/homer.shr'
FALL_Y = -30.0
DEATH_CASE = 'g4_001_'   # прыжок с моста l1r7 через перила в канал (зона DEATH R7D06)
TR = re.compile(r'кадр (\d+) (\S+) (\S+) (\S+) (\S+) на земле (\d)')


def frames(p):
    out = []
    for ln in Path(p).read_text().splitlines():
        if ln.startswith('#') or not ln.strip(): continue
        n, b, ax, ay = ln.split(); out.append((int(n), int(b, 16), float(ax), float(ay)))
    return out


def variant(p, rot=0.0, k=1.0, flip_run=False):
    """тот же ввод: стик повёрнут на rot градусов и умножен на k, бег (○) переключён"""
    head = Path(p).read_text().split('\n', 1)[0]
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot)); L = [head]
    for n, b, ax, ay in frames(p):
        x, y = (ax * c - ay * s) * k, (ax * s + ay * c) * k
        if flip_run and (ax or ay): b ^= 0x2000
        L.append(f'{n} {b:x} {x:.6g} {y:.6g}')
    return '\n'.join(L) + '\n'


def run(binp, path, env=None):
    s = re.search(r'--start (\S+) (\S+) (\S+) (\S+)', Path(path).read_text().split('\n', 1)[0]).groups()
    r = subprocess.run([str(binp), str(LVL), str(HOM), '--input', str(path), '--start', *s], capture_output=True, text=True,
                       env=dict(os.environ, GH_TRACE='1', **(env or {})))
    rows = [(int(m[1]), m[2], float(m[3]), float(m[4]), float(m[5]), int(m[6])) for m in TR.finditer(r.stderr)]
    if not rows: return dict(err=r.stderr[-200:] or 'нет строк трассы')
    ymin = min(q[3] for q in rows)
    drops = 0; top = None   # законные падения: в воздухе с высоты, приземлился на 2+ м ниже
    for a, b in zip(rows, rows[1:]):
        if a[5] and not b[5]: top = a[3]
        if b[5] and top is not None:
            if top - b[3] >= 2.0 and b[3] > FALL_Y: drops += 1
            top = None
    tele = any(a[1] == b[1] == 'Гомер' and math.dist(a[2:5], b[2:5]) > 5 for a, b in zip(rows, rows[1:]))
    return dict(fell=ymin < FALL_Y, ymin=ymin, drops=drops, tele=tele)


def main():
    green, red = Path(sys.argv[1]), Path(sys.argv[2])
    reps = sorted((ROOT / 'tests/bots/regress').glob('g4_*.in'))
    if len(reps) < 20: print(f'нет повторов: {len(reps)} < 20'); return 1
    tmp = ROOT / 'build/tmp/falls'; tmp.mkdir(parents=True, exist_ok=True)
    vars_ = []
    for p in reps:
        for j, (rot, k, fr) in enumerate([(10, 1, 0), (-10, 1, 0), (20, 1, 0), (-20, 1, 0), (0, .7, 0), (0, 1, 1)]):
            q = tmp / f'{p.stem}_v{j}.in'; q.write_text(variant(p, rot, k, fr)); vars_.append(q)
    jobs = [('green', green, p, None) for p in reps + vars_] + [('red_void', red, p, None) for p in reps] + \
           [('red_death', green, p, {'BW_NO_DEATH': '1'}) for p in reps] + [('red_both', red, p, {'BW_NO_DEATH': '1'}) for p in reps + vars_]
    with ThreadPoolExecutor(os.cpu_count() or 4) as ex: res = list(ex.map(lambda j: (j[0], j[2], run(j[1], j[2], j[3])), jobs))
    R = {}
    for kind, p, r in res: R.setdefault(kind, {})[p.name] = r
    errs = [(k, n, r['err']) for k in R for n, r in R[k].items() if 'err' in r]
    if errs: print('ошибки прогона:', errs[:3]); return 1
    ok = True
    names = [p.name for p in reps]
    for n in names:
        g, rv, rd, rb = R['green'][n], R['red_void'][n], R['red_death'][n], R['red_both'][n]
        red_any = rv['fell'] or rd['fell']
        line = (f"{n[:44]:44s} старый код: {'ПРОВАЛ' if rb['fell'] else 'нет'} ({rb['ymin']:.0f} м) · без стены: {'ПРОВАЛ' if rv['fell'] else 'нет'} · "
                f"без DEATH: {'ПРОВАЛ' if rd['fell'] else 'нет'} · новый: {'ПРОВАЛ' if g['fell'] else 'нет'} ({g['ymin']:.1f} м)")
        if g['fell'] or not rb['fell'] or not red_any: ok = False; line += '  <-- FAIL'
        print(line)
    vn = [q.name for q in vars_]
    gv = sum(R['green'][n]['fell'] for n in vn); rvv = sum(R['red_both'][n]['fell'] for n in vn)
    print(f'соседние варианты (±10°, ±20°, ×0.7, бег↔шаг): {len(vn)} шт.; провалов: старый код {rvv}, новый {gv}')
    if gv or not rvv: ok = False; print('  <-- FAIL: новый код проваливается' if gv else '  <-- FAIL: варианты не доходят до краёв (старый не падает)')
    drops = sum(R['green'][n]['drops'] for n in names + vn)
    print(f'законные падения ≥ 2 м с приземлением в новом коде: {drops}')
    if drops == 0: ok = False; print('  <-- FAIL: правило запирает законные падения')
    dc = next(n for n in names if n.startswith(DEATH_CASE)); t = R['green'][dc]['tele']
    print(f'прыжок с моста l1r7 в канал: зона DEATH возвращает Гомера — {"да" if t else "НЕТ"}')
    if not t: ok = False; print('  <-- FAIL')
    print('PASS' if ok else 'FAIL'); return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""№942 гейт: появление пузыря сообщения. Читает smoke.txt прогона (строки UIBUB942, UIWRAP942 при uiTrace POP).
  check.py pop  DIR   кадры по возрасту (сценарий pop_scenario.txt, часы HUD стоят): текст и аватар не растут с рамкой
  check.py wrap DIR   перенос строк считается один раз на текст и ширину
  check.py lag  DIR   подвисший кадр (lag_scenario.txt): шаг возраста за кадр не больше 0,05 с
Код выхода 0 — PASS."""
import re, sys
from pathlib import Path

ROW = re.compile(r'UIBUB942 age=(\S+) part=(\w) x0=(\S+) y0=(\S+) x1=(\S+) y1=(\S+) a=(\S+) wrapw=(-?\d+) nl=(-?\d+)')

def rows(d):
    out = []
    for m in ROW.finditer((Path(d) / 'smoke.txt').read_text()):
        g = m.groups(); out.append(dict(age=float(g[0]), part=g[1], x0=float(g[2]), y0=float(g[3]), x1=float(g[4]), y1=float(g[5]), a=float(g[6]), w=int(g[7]), nl=int(g[8])))
    return out

def sequences(rs):
    """строки одного появления: возраст растёт; падение возраста больше чем на 0,3 — новое сообщение"""
    seqs, cur, last = [], [], None
    for r in rs:
        if last is not None and r['age'] < last - 0.3:
            seqs.append(cur); cur = []
        cur.append(r); last = r['age']
    if cur: seqs.append(cur)
    return [s for s in seqs if any(r['part'] == 't' for r in s)]

def pop(d):
    seqs = sequences(rows(d)); bad = []; info = []
    if len(seqs) < 4: return f'FAIL: найдено {len(seqs)} появлений из 4'
    for k, s in enumerate(seqs[:4]):
        tx = [r for r in s if r['part'] == 't']; fr = [r for r in s if r['part'] == 'f']; av = [r for r in s if r['part'] == 'a']
        tw = [r['x1'] - r['x0'] for r in tx]; wf = max(tw); fw = max(r['x1'] - r['x0'] for r in fr)
        first = tx[0]; final = tx[-1]
        # 1: колонка текста с первого видимого кадра равна конечной (ширина, число строк, ширина переноса)
        if tw[0] < 0.97 * wf: bad.append(f'#{k}: в первом кадре текста ширина {tw[0]:.0f} от конечных {wf:.0f} (узкая колонка)')
        if any(r['w'] != final['w'] or r['nl'] != final['nl'] for r in tx): bad.append(f'#{k}: перенос строк менялся по кадрам ({sorted(set((r["w"], r["nl"]) for r in tx))})')
        if any(abs((r['y1'] - r['y0']) - (final['y1'] - final['y0'])) > 1 for r in tx): bad.append(f'#{k}: высота текста менялась по кадрам')
        # 2: рамка раскрылась раньше текста
        fat = [r for r in fr if abs(r['age'] - first['age']) < 1e-3 or r['age'] <= first['age']]
        wnow = max((r['x1'] - r['x0'] for r in fat), default=0)
        if wnow < 0.99 * fw: bad.append(f'#{k}: текст появился при рамке {wnow:.0f} из {fw:.0f} px (раньше раскрытия)')
        # 3: фейд и короткий слайд справа налево
        if not (first['a'] < 0.9 and final['a'] >= 0.99): bad.append(f'#{k}: нет проявления (альфа {first["a"]:.2f} -> {final["a"]:.2f})')
        dx = first['x0'] - final['x0']
        if not (3 <= dx <= 9): bad.append(f'#{k}: слайд текста {dx:.1f} px (нужно 3..9, справа налево)')
        # 4: аватар стоит на месте с первого кадра, без переезда
        if av:
            ax = [(r['x0'], r['y0'], r['x1'], r['y1']) for r in av]; ref = ax[-1]
            if max(max(abs(a - b) for a, b in zip(t, ref)) for t in ax) > 1.01: bad.append(f'#{k}: аватар переезжает по кадрам (сдвиг до {max(max(abs(a - b) for a, b in zip(t, ref)) for t in ax):.0f} px)')
            if min(r['age'] for r in av) < 0.16 - 1e-3: bad.append(f'#{k}: аватар виден раньше раскрытия рамки (возраст {min(r["age"] for r in av):.2f})')
        info.append(f'#{k}: текст {tw[0]:.0f}/{wf:.0f}px с возраста {first["age"]:.2f}, слайд {dx:.0f}px, аватар {"есть" if av else "нет"}')
    print('  замер:', '; '.join(info))
    return 'PASS' if not bad else 'FAIL: ' + '; '.join(bad)

def wrap(d):
    n = len(re.findall(r'UIWRAP942 calc=', (Path(d) / 'smoke.txt').read_text()))
    print(f'  замер: переносов строк пузыря за прогон (4 текста, ~100 кадров): {n}')
    return 'PASS' if n <= 6 else f'FAIL: перенос считался {n} раз (нужно не больше 6: по разу на текст)'

def lag(d):
    rs = [r for r in rows(d) if r['part'] == 'f']; seqs = []; cur = []; last = None
    for r in rs:
        if last is not None and r['age'] < last - 0.3: seqs.append(cur); cur = []
        cur.append(r); last = r['age']
    seqs.append(cur)
    steps = []
    for s in seqs:
        ages = sorted(set(round(r['age'], 4) for r in s if r['age'] <= 0.5))
        steps += [b - a for a, b in zip(ages, ages[1:])]
    mx = max(steps, default=9)
    print(f'  замер: самый большой шаг возраста за кадр при подвисшем кадре 0,35 с: {mx:.3f} с')
    return 'PASS' if mx <= 0.05 else f'FAIL: шаг возраста {mx:.3f} с (анимация перепрыгнула шаги)'

if __name__ == '__main__':
    r = globals()[sys.argv[1]](sys.argv[2]); print(r); sys.exit(0 if r == 'PASS' else 1)

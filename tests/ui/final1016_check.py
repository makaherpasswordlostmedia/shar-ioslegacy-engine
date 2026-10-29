#!/usr/bin/env python3
"""Проверки кадров гейта tests/ui/final1016_gate.sh (№623, №630, №638, №640/№646). Каждая принимает папку прогона сценария (снимки *.png и smoke.txt) и печатает
«PASS»/«FAIL: причина»; код выхода 0 = PASS.   final1016_check.py pop DIR | bubble DIR | race DIR"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image

def img(d, n):
    return np.asarray(Image.open(Path(d) / f'{n}.png').convert('RGB')).astype(int)

def pop(d):
    """№638: появление бабла — рамка растёт единым масштабом по ширине и высоте (не только по высоте). Строки UIPOP из smoke.txt первого всплывания"""
    rows = [dict(zip(('age', 'w', 'h'), (float(m.group(1)), float(m.group(2)), float(m.group(3)))))
            for m in re.finditer(r'UIPOP t=\S+ tag=(\d+) on=1 age=(\S+) w=(\S+) h=(\S+)', (Path(d) / 'smoke.txt').read_text())
            for m in [re.match(r'(\S+) (\S+) (\S+)', f'{m.group(2)} {m.group(3)} {m.group(4)}')] if m]
    if len(rows) < 6: return f'FAIL: мало строк UIPOP ({len(rows)})'
    rows = rows[:40]; fin = rows[-1]; wf, hf = fin['w'], fin['h']
    rw0, rh0 = rows[0]['w'] / wf, rows[0]['h'] / hf
    bad = []
    if rw0 > .8: bad.append(f'в первом кадре ширина уже {rw0:.2f} от конечной (рост только по высоте)')
    for r in rows[:4]:
        rw, rh = r['w'] / wf, r['h'] / hf
        if abs(rw - rh) > .08: bad.append(f'age {r["age"]:.2f}: ширина {rw:.2f} против высоты {rh:.2f} от конечных'); break
    return 'PASS' if not bad else 'FAIL: ' + '; '.join(bad)

def frame_text(a):
    """рамка бабла (кремовая кайма) и жёлтый текст внутри, область нижнего левого бабла 480x272"""
    y0, x0 = 160, 35; sub = a[y0:250, x0:335]
    txt = (sub[..., 0] > 245) & (sub[..., 1] > 245) & (sub[..., 2] < 24)
    bd = (sub[..., 0] >= 215) & (sub[..., 0] <= 250) & (sub[..., 1] >= 185) & (sub[..., 1] <= 240) & (sub[..., 2] >= 60) & (sub[..., 2] <= 200)
    gy, gx = np.where(bd); ty, tx = np.where(txt)
    return [int(gy.min() + y0), int(gy.max() + y0), int(gx.min() + x0), int(gx.max() + x0)], [int(ty.min() + y0), int(ty.max() + y0), int(tx.min() + x0), int(tx.max() + x0)]

def bubble(d):
    """№640: поля текста в бабле равны слева/справа (≤ 8 px) и сверху/снизу у 1–2 строк (≤ 8 px). №646: рамка с 4 строками выше рамки с 2 строками (≥ 12 px),
    поле снизу у 4 строк не меньше 10 px"""
    m = {}
    for n in ('l1', 'l2', 'l4'):
        f, t = frame_text(img(d, n)); m[n] = dict(h=f[1] - f[0], top=t[0] - f[0], bot=f[1] - t[1], lr=(t[2] - f[2]) - (f[3] - t[3]))
    bad = []
    for n in ('l1', 'l2', 'l4'):
        if abs(m[n]['lr']) > 8: bad.append(f'{n}: поля слева/справа различаются на {abs(m[n]["lr"])} px')
    for n in ('l1', 'l2'):
        if abs(m[n]['top'] - m[n]['bot']) > 8: bad.append(f'{n}: поля сверху/снизу {m[n]["top"]}/{m[n]["bot"]} px')
    if m['l4']['h'] < m['l2']['h'] + 12: bad.append(f'рамка 4 строк {m["l4"]["h"]} px не выше рамки 2 строк {m["l2"]["h"]} px')
    if m['l4']['bot'] < 10: bad.append(f'поле снизу у 4 строк {m["l4"]["bot"]} px')
    print('  замер:', {k: (v['h'], v['top'], v['bot'], v['lr']) for k, v in m.items()}, '(h, верх, низ, лево-право)')
    return 'PASS' if not bad else 'FAIL: ' + '; '.join(bad)

def race(d):
    """№623: до взлёта кружка цели в углу виден значок дома (кремовое кольцо в углу) и блок таймера правее него (левый край цифр ≥ 108 px).
    №630: на слове отсчёта («GO!») зелёные буквы по центру экрана (в прежнем коде слово в нижнем пузыре жёлтым)"""
    bad = []; info = []
    for n in ('c1', 'd0'):
        a = img(d, n)
        ring = (a[..., 0] >= 215) & (a[..., 0] <= 250) & (a[..., 1] >= 185) & (a[..., 1] <= 240) & (a[..., 2] >= 60) & (a[..., 2] <= 200)
        t = (a[..., 0] >= 200) & (a[..., 1] >= 140) & (a[..., 1] <= 200) & (a[..., 2] >= 20) & (a[..., 2] <= 90) & (a[..., 0] - a[..., 1] >= 30)
        sub = t[22:56, 5:330]; cols = sub.sum(0); idx = [i for i, c in enumerate(cols) if c >= 4]; left = idx[0] + 5 if idx else -1
        rc = int(ring[15:85, 10:112].sum()); info.append(f'{n}: кольцо {rc}, таймер слева {left}')
        if rc < 400: bad.append(f'{n}: нет значка дома (кольцо {rc} < 400)')
        if left < 108: bad.append(f'{n}: блок таймера не правее значка дома (слева {left} px)')
    g = []
    for n in [f'd{i}' for i in range(8)]:
        a = img(d, n); gm = (a[..., 1] > 170) & (a[..., 0] < 90) & (a[..., 2] < 90); g.append(int(gm[95:165, 150:340].sum()))
    info.append(f'зелёное в центре по кадрам d0..d7: {g}')
    if max(g) < 150: bad.append(f'слово отсчёта не зелёное по центру (максимум {max(g)} < 150)')
    print('  замер:', '; '.join(info))
    return 'PASS' if not bad else 'FAIL: ' + '; '.join(bad)

if __name__ == '__main__':
    r = globals()[sys.argv[1]](sys.argv[2]); print(r); sys.exit(0 if r == 'PASS' else 1)

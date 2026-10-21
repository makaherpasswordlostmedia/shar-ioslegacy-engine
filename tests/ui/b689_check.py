#!/usr/bin/env python3
"""Гейт №689 (Роб 17.10): все баблы сообщений — один вид: рамка левее радара и не выше его верха, текст слева, рамка по ширине текста (не шире текста более чем на поле),
не квадратная. Меряется по кадрам эмулятора 480x272 (сценарий b689_msgs_scenario.txt): золотая рамка (кроме радара x >= 380) и жёлтый текст внутри.
   b689_check.py ПАПКА_КАДРОВ           -> 0: все кадры в норме
   b689_check.py --red ПАПКА_КАДРОВ     -> 0 только если на этой (прежней) сборке нарушение есть (красный контроль)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
SHOTS = ['a_talk', 'b_dest', 'c_m2', 'd_m3', 'e_m5', 'f_m6', 'g_long']
ICON_SHOTS = ('a_talk', 'e_m5', 'f_m6')   # с аватаром или малым значком
RADAR_X, RADAR_TOP = 380, 168      # радар справа: рамка правее 380 — на радаре; выше 168 — выше верха радара (кольцо радара начинается ≈ y 181, рамка пакета 175)
def measure(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)[:, :RADAR_X]
    gold = (a[..., 0] > 140) & (a[..., 1] > 90) & (a[..., 0] - a[..., 2] > 80) & (a[..., 0] - a[..., 1] < 90)   # золото рамки (светлое и тёмное)
    gold[:150] = False
    ys, xs = np.nonzero(gold)
    if len(xs) < 50: return None
    # рамка: нижняя горизонталь золота (самая нижняя строка с протяжённым золотом) и верхняя
    rows = np.nonzero(gold.sum(1) > 40)[0]
    top, bot = rows.min(), rows.max()
    cols = np.nonzero(gold[top:bot + 1].sum(0) > 4)[0]
    left, right = cols.min(), cols.max()
    inner = a[top + 8:bot - 7, left + 14:right - 14]
    txt = (inner[..., 0] > 225) & (inner[..., 1] > 225) & (inner[..., 2] < 150)
    ty, tx = np.nonzero(txt)
    if len(tx) < 20: return None
    allc = (inner[..., 0] > 200) & (inner[..., 1] > 200) & (inner[..., 2] < 160)   # №689: зазор значок→текст: самый широкий пустой промежуток столбцов внутри строки (значок слева, текст правее)
    cs = np.nonzero(allc.any(0))[0]; gap = int(np.diff(cs).max()) if len(cs) > 1 else 0
    c0 = np.nonzero(gold[top])[0]; sc0 = int(c0.min() - left) if len(c0) else 0   # №710: где на верхней строке рамки начинается золото = радиус скругления
    return dict(sc0=sc0, gap=gap, left=left, right=right, top=top, bot=bot, tl=tx.min() + left + 14, tr=tx.max() + left + 14, tt=ty.min() + top + 8)
def verdict(m, n=''):
    bad = []
    if m['right'] > RADAR_X - 4: bad.append(f"рамка заходит на радар (правый край {m['right']})")
    if m['top'] < RADAR_TOP: bad.append(f"рамка выше верха радара (верх {m['top']})")
    if n in ICON_SHOTS:   # №708: пузырь с аватаром: текст кончается до скругления капсулы (24 px) с зазором: справа от текста не меньше 26 px
        if m['right'] - m['tr'] < 26: bad.append(f"текст заходит на скруглённый край: справа от текста {m['right'] - m['tr']} px (нужно >= 26)")
    elif n:   # №710: пузырь без аватара у левого поля экрана (как пузырь с аватаром, x 19) и скругление растёт с высотой (полукруг)
        if m['left'] > 24: bad.append(f"рамка без аватара не у левого поля: левый край {m['left']} (нужно <= 24)")
        if m['bot'] - m['top'] >= 55 and m['sc0'] < 0.42 * (m['bot'] - m['top']): bad.append(f"малый радиус скругления у высокой рамки: {m['sc0']} px на высоте {m['bot'] - m['top']}")
    if m['right'] - m['tr'] > (22 if n not in ICON_SHOTS else 40): bad.append(f"рамка шире текста: справа от текста {m['right'] - m['tr']} px")
    if m['gap'] > 30: bad.append(f"зазор между значком и текстом {m['gap']} px (у аватара ≈ 8)")
    w, h = m['right'] - m['left'], m['bot'] - m['top']
    if w < 1.4 * h: bad.append(f"рамка квадратная: {w}x{h}")
    return bad
red = sys.argv[1] == '--red'; d = Path(sys.argv[2] if red else sys.argv[1]); allbad = []
for n in SHOTS:
    m = measure(d / f'{n}.png')
    if not m: allbad.append(f'{n}: рамка/текст не найдены'); print(n, 'нет рамки'); continue
    b = verdict(m, n); print(f"{n}: рамка x {m['left']}..{m['right']} y {m['top']}..{m['bot']}, текст x {m['tl']}..{m['tr']}", '; '.join(b) or 'ok')
    allbad += [f'{n}: {x}' for x in b]
if red: sys.exit(0 if allbad else 1)
sys.exit(1 if allbad else 0)

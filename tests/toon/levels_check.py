"""№428: кадры мультика L2–L7 (tests/toon/levels_scenario.txt, запуск tests/toon/levels.sh DIR). Проверки по журналу smoke.txt и кадрам:
1) на КАЖДОМ кадре LN_t0/LN_t1 активный уровень = N и герой (префикс клипов PLAYER) тот, что ждём (L2 brt_, L3 lsa_, L4 mrg_, L5 apu_, L6 brt_, L7 hom_) — иначе красный
   (первый лист 16.10 был целиком с L1: SHIP_LEVELS пуст, golevel молча пропущен, а гейт считал чёрные пиксели и был зелёным);
2) контур есть (чёрных пикселей вкл больше, чем выкл, на > 100) и нет клякс (прирост < 10% кадра: у крупного плана Мардж L4 честные 6%, у старой кляксы v2 было 16%).
Пишет лист OUT/levels_sheet.png: на уровень — выкл и вкл целиком, вырезка героя x3 выкл и вкл; подпись из журнала."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
d = Path(sys.argv[1]); WANT = {2: 'brt_', 3: 'lsa_', 4: 'mrg_', 5: 'apu_', 6: 'brt_', 7: 'hom_'}
level = pre = None; shots = {}
for ln in (d / 'smoke.txt').read_text(errors='replace').splitlines():
    m = re.match(r'PLAYER ev=\w+ level=(\d+) file=(\S+) pre=(\S+)', ln)
    if m: level, pre = int(m.group(1)), m.group(3)
    m = re.match(r'LEVEL ev=load n=(\d+)', ln)
    if m: level = int(m.group(1))
    m = re.match(r'SHOT (\S+) ', ln)
    if m: shots[m.group(1)] = (level, pre)
def blk(n):
    a = np.asarray(Image.open(d / f'{n}.png').convert('RGB')).astype(int); return int((a.max(2) < 24).sum()), a.shape[0] * a.shape[1]
bad = 0; rows = []
for N in range(2, 8):
    for t in ('t0', 't1'):
        lv, pr = shots.get(f'L{N}_{t}', (None, None))
        if lv != N or pr != WANT[N]:
            bad += 1; print(f'L{N}_{t}: FAIL на кадре уровень {lv}, герой {pr} (ждали {N}, {WANT[N]})')
    b0, tot = blk(f'L{N}_t0'); b1, _ = blk(f'L{N}_t1'); gain = b1 - b0
    ok = gain > 100 and gain < tot * .10; bad += not ok
    print(f'L{N} ({shots.get(f"L{N}_t0", (None, None))[1]}): чёрных выкл {b0}, вкл {b1}, прирост {gain} ({100.0 * gain / tot:.2f}% кадра) {"OK" if ok else "FAIL"}')
    rows.append(N)
try:
    W, H = 480, 272; cw, ch = 140, 110; sheet = Image.new('RGB', (W * 2 + cw * 3 * 2, 300), (24, 24, 24)); sheet = Image.new('RGB', (W * 2 + cw * 6, 300 * len(rows)), (24, 24, 24))
    for i, N in enumerate(rows):
        x = 0
        for t in ('t0', 't1'):
            im = Image.open(d / f'L{N}_{t}.png').convert('RGB').resize((W, H)); sheet.paste(im, (x, i * 300)); x += W
        for t in ('t0', 't1'):
            im = Image.open(d / f'L{N}_{t}.png').convert('RGB').resize((W, H)).crop((W // 2 - cw // 2, H // 2 - 10, W // 2 + cw // 2, H // 2 - 10 + ch)).resize((cw * 3, ch * 3), Image.NEAREST)
            sheet.paste(im, (x, i * 300)); x += cw * 3
        pr = shots.get(f'L{N}_t0', (None, '?'))[1]; ImageDraw.Draw(sheet).text((6, i * 300 + 4), f'L{N} {pr}  off | on | x3 off | x3 on', fill=(255, 255, 0))
    sheet.save(d / 'levels_sheet.png'); print('лист:', d / 'levels_sheet.png')
except Exception as e:
    print('лист не собран:', e)
sys.exit(1 if bad else 0)

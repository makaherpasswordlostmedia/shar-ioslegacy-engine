#!/usr/bin/env python3
"""Сверка прогона tests/menu/access_scenario.txt (пункт ДОБИВКИ 26) с записями PS2 ~/Downloads/shar-psp-ps2-w/build/twins/o4/
ps2_access_pause, ps2_access_options_unlock, ps2_access_settings_unlock (факт knowledge/facts/ps2-menu-access.yaml).
  access_check.py RUN_DIR [--expect-fail ms|start|rows]   -> первая строка итог; код 0 = OK (с --expect-fail: 0, если упала нужная проверка)
Проверки (строки smoke.txt движка viewer/main.c и снимки):
  rows  — снимок паузы ac_pause по пикселям против кадра PS2 ps2_access_pause shot_120 (sha256 из факта): одним разбором
          (pause_rows: жёлтая строка курсора, дальше 6 строк с найденным шагом, белая / серая по белым пикселям) обе картинки
          обязаны дать одно и то же — CONTINUE жёлтый, MISSION SELECT серый, LEVEL PROGRESS .. QUIT GAME белые (SAVE GAME тоже:
          на PS2 он белый; в служебном смоуке он белый только с «flag saves», tests/menu/access_scenario.txt); плюс в PAUSEKEY
          выключен только бит 2 (MISSION SELECT)
  ms    — пауза на новой игре L1 (m0sd): MISSION SELECT выключен (PAUSEKEY off, бит 2), ↓↓↓ + ✕ из CONTINUE = OPTIONS
          (PAUSEACT act=5 и OPT pack=pmenu scr=0), как PS2 shot_80/120 -> shot_150
  start — ↓ + ✕ = SETTINGS (OPT scr=2); START на SETTINGS закрывает паузу: до снимка ac_game нет паузы, следующий START
          открывает её снова (PAUSE on между ac_game и ac_pause2), как PS2 кадр 340 -> 400"""
import hashlib, os, sys
from pathlib import Path
import numpy as np
from PIL import Image

PS2W = Path(os.environ.get('PS2W', Path.home() / 'Downloads/shar-psp-ps2-w'))
PS2_PAUSE = PS2W / 'build/twins/o4/ps2_access_pause/shot_120.png'
PS2_PAUSE_SHA = 'c19b149b6ec2db1c822648d4998029b1c56124bc70f41346537ad953e5147571'   # knowledge/facts/ps2-menu-access.yaml


def pause_rows(path, box=(0.32, 0.15, 0.68, 0.95), n=7):
    """строки меню паузы на снимке (любое разрешение): первая жёлтая полоса текста (курсор на CONTINUE; горизонталь рамки и
    мелкие жёлтые пятна сцены отсеяны по ширине), дальше n-1 строк с шагом, при котором белых пикселей в окнах больше всего;
    строка белая, если белых (min RGB > 215) в окне больше 2 на строку высоты, иначе серая -> (['yellow', ...], пояснение)"""
    a = np.asarray(Image.open(path).convert('RGB')).astype(int); H, W = a.shape[:2]
    x0, y0, x1, y1 = int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)
    c = a[y0:y1, x0:x1]; R, G, B = c[..., 0], c[..., 1], c[..., 2]
    yel = ((R > 170) & (G > 140) & (B < 120) & (R - B > 90)).sum(1); wht = (np.minimum(np.minimum(R, G), B) > 215).sum(1)
    on = list((yel > 0.12 * (x1 - x0)) & (yel < 0.6 * (x1 - x0))) + [False]
    bands = []; s = None; gap = 0; last = 0
    for y, v in enumerate(on):
        if v: s = y if s is None else s; gap = 0; last = y
        elif s is not None:
            gap += 1
            if gap > 4: bands.append((s, last + 1)); s = None
    bands = [b for b in bands if b[1] - b[0] >= 5]
    if not bands: return None, 'нет жёлтой строки'
    top, bot = bands[0]; h = bot - top
    if h > 40: return None, 'жёлтая полоса %d px' % h
    best, pitch = -1, 0
    for p in range(int(h * 1.3), int(h * 3.5) + 1):
        sc = sum(min(wht[top + k * p: bot + k * p].sum(), 50 * h) for k in range(1, n))
        if sc > best: best, pitch = sc, p
    out = ['yellow'] + ['white' if wht[top + k * pitch: bot + k * pitch].sum() > 2 * h else 'grey' for k in range(1, n)]
    return out, 'строка y %d..%d, шаг %d' % (y0 + top, y0 + bot, pitch)

run = Path(sys.argv[1]); exp = sys.argv[sys.argv.index('--expect-fail') + 1] if '--expect-fail' in sys.argv else None
log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
idx = {l.split()[1]: i for i, l in enumerate(log) if l.startswith('SHOT ')}
fail = {'ms': [], 'start': [], 'rows': []}
need = ('ac_pause', 'ac_options', 'ac_settings', 'ac_game', 'ac_pause2')
miss = [s for s in need if s not in idx or not (run / f'{s}.png').exists()]
if miss or not any(l.startswith('END') for l in log):
    print('FAIL прогон неполный: ' + ', '.join(miss or ['нет END'])); sys.exit(2)
seg = lambda a, b: log[idx[a]:idx[b]]
keys = [l for l in seg('ac_pause', 'ac_options') if l.startswith('PAUSEKEY')]
off = [int(l.split('off=')[1].split()[0], 16) for l in keys]
if off and any(o & ~(1 << 2) & 0xff for o in off): fail['rows'].append('кроме MISSION SELECT выключены пункты (PAUSEKEY off=%s; бит 6 — SAVE GAME)' % ','.join('%x' % o for o in off))
if not PS2_PAUSE.exists() or hashlib.sha256(PS2_PAUSE.read_bytes()).hexdigest() != PS2_PAUSE_SHA:
    fail['rows'].append('нет кадра PS2 %s с sha256 факта' % PS2_PAUSE)
else:
    ps2, ps2i = pause_rows(PS2_PAUSE); prt, prti = pause_rows(run / 'ac_pause.png')
    rows_info = 'PS2 %s (%s); порт %s (%s)' % (ps2, ps2i, prt, prti)
    if ps2 != prt: fail['rows'].append('пауза по пикселям не как PS2 shot_120: ' + rows_info)
if not off or not all(o >> 2 & 1 for o in off): fail['ms'].append('MISSION SELECT не выключен (PAUSEKEY off=%s)' % ','.join('%x' % o for o in off))
opt = seg('ac_pause', 'ac_options')
if not any(l.startswith('PAUSEACT act=5') for l in opt) or not any(l.startswith('OPT pack=pmenu scr=0') for l in opt):
    got = [l.split(' t=')[0] for l in opt if l.startswith(('PAUSEACT', 'VIEWCARDS open', 'MSNSEL'))]
    fail['ms'].append('↓↓↓ + ✕ не OPTIONS (%s)' % ('; '.join(got) or 'ничего'))
if not fail['ms']:   # START проверяем, только когда путь дошёл до SETTINGS
    if not any(l.startswith('OPT pack=pmenu scr=2') for l in seg('ac_options', 'ac_settings')):
        fail['start'].append('↓ + ✕ не открыл SETTINGS (нет OPT scr=2)')
    elif not any(l.startswith('PAUSE on') for l in seg('ac_game', 'ac_pause2')):
        fail['start'].append('START на SETTINGS не закрыл паузу (следующий START не открыл её снова)')
bad = [k for k in fail if fail[k]]
line = '; '.join('%s: %s' % (k, ', '.join(fail[k])) for k in bad)
if exp:
    ok = exp in bad and all(k == exp for k in bad) if exp == 'start' else exp in bad
    print(('OK красный %s пойман: ' % exp + line) if ok else 'FAIL красный %s не пойман: %s' % (exp, line or 'всё прошло')); sys.exit(0 if ok else 1)
print(('OK' if not bad else 'FAIL ' + line) + ' · menu access emu (%s)' % run.name)
print('  пауза по пикселям: ' + globals().get('rows_info', 'не сверялась'))
for l in log:
    if l.startswith(('PAUSEMS', 'PAUSEKEY', 'PAUSEACT', 'PAUSESUB', 'OPT pack=pmenu', 'PAUSE on')): print('  ' + l.split(' vol=')[0])
sys.exit(1 if bad else 0)

#!/usr/bin/env python3
"""Сверка прогона tests/tone/scenario.txt (правка Роба 144): строки OPT экрана Settings паузы (scr=2), строки TONE, снимки.
  · строка Colour есть и включена; colour: 136 -> 160 (седьмое ► без перескока) -> 100 (лишнее ◄ без перескока) -> 136
  · каждое изменение — строка TONE: палитр >= 500, miss=0, err=0 (палитры перечитаны из файлов)
  · снимки мира: насыщенность кадра 1.60 > 1.36 > 1.00; повторный 1.36 близок к первому
    python tests/tone/check.py ОТЧЁТ_СМОУКА   -> PASS / FAIL (код 1)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def kv(parts):
    return dict(p.split('=', 1) for p in parts if '=' in p)


def chroma(png):
    a = np.asarray(Image.open(png).convert('RGB'), np.int16)
    a = a[a.shape[0] // 6: a.shape[0] * 3 // 4]   # без HUD сверху и снизу
    return float((a.max(2) - a.min(2)).mean())


def main():
    out = Path(sys.argv[1]); log = (out / 'smoke.txt').read_text(errors='replace').splitlines()
    fails = []
    opt = [kv(l.split()[1:]) for l in log if l.startswith('OPT ') and ' scr=2 ' in l]
    cols = [int(d['colour']) for d in opt if 'colour' in d]
    seq = [c for i, c in enumerate(cols) if i == 0 or c != cols[i - 1]]
    ext = seq[:1] + [b for a, b, c in zip(seq, seq[1:], seq[2:]) if (b - a) * (c - b) < 0] + seq[-1:]   # точки разворота
    if ext != [136, 160, 100, 136]: fails.append('насыщенность в Settings: развороты %s (ждём 136 -> 160 -> 100 -> 136)' % ext)
    if cols and (max(cols) > 160 or min(cols) < 100): fails.append('вне диапазона 1.00..1.60: %s' % sorted(set(cols)))
    # перескок: после 160 сразу 100 (или наоборот) — строка вариантов пошла по кругу
    jumps = [(a, b) for a, b in zip(seq, seq[1:]) if abs(a - b) > 4]
    if jumps: fails.append('перескок значения: %s' % jumps[:3])
    tone = [kv(l.split()[1:]) for l in log if l.startswith('TONE ')]
    if not tone: fails.append('нет строк TONE (палитры не пересчитывались)')
    badt = [d for d in tone if int(d['pal']) < 500 or d['miss'] != '0' or d['err'] != '0']
    if badt: fails.append('TONE с ошибкой: %s' % badt[:2])
    shots = {n: out / (n + '.png') for n in ('tone_136', 'tone_160', 'tone_100', 'tone_136b')}
    miss = [n for n, p in shots.items() if not p.exists()]
    if miss: fails.append('нет снимков: ' + ', '.join(miss))
    else:
        c = {n: chroma(p) for n, p in shots.items()}
        step = c['tone_160'] - c['tone_136']
        if not (c['tone_160'] > c['tone_136'] > c['tone_100']): fails.append('насыщенность кадров не по порядку: %s' % {k: round(v, 2) for k, v in c.items()})
        elif abs(c['tone_136b'] - c['tone_136']) > max(.5, .5 * step): fails.append('повторный 1.36 не вернулся: %.2f против %.2f' % (c['tone_136b'], c['tone_136']))
        print('кадры, средняя хрома: ' + ', '.join('%s %.2f' % (k, v) for k, v in c.items()))
    ms = [int(d['ms']) for d in tone]
    if fails:
        print('tone: FAIL — ' + '; '.join(fails)); return 1
    print('tone: PASS — Colour %s, пересчётов %d (палитр %s, %d..%d мс)' % (ext, len(tone), tone[0]['pal'], min(ms), max(ms)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

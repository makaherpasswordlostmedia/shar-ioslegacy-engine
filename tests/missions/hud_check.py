#!/usr/bin/env python3
"""Сверка HUD миссий по smoke.txt (tests/missions/emu_hud.sh): оверлеи (UIOV) не пересекаются, тексты (UIFIT) влезают.
   hud_check.py SMOKE_TXT RC_СМОУКА -> код 0 = ок"""
import re, sys

log = open(sys.argv[1], encoding='utf-8', errors='replace').read().splitlines()
rc = int(sys.argv[2]) if len(sys.argv) > 2 else 0
ov = [tuple(map(int, m.groups())) for m in (re.match(r'UIOV tag=(\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)', l) for l in log) if m]
nov = [int(m.group(1)) for m in (re.match(r'UIOV n=(\d+)', l) for l in log) if m]
fit = [l for l in log if l.startswith('UIFIT ')]
tot = [tuple(map(int, m.groups())) for m in (re.match(r'UIFIT total=(\d+) over=(\d+)', l) for l in fit) if m]
names = {6: 'таймер', 7: 'пар-время', 8: 'круги', 9: 'место', 24: 'счётчик'}
ok = True
print('оверлеи:', ', '.join(f'{names.get(t, t)} {x0},{y0}-{x1},{y1}' for t, x0, y0, x1, y1 in ov) or '-')
if not nov or nov[-1] < 2:
    print('оверлеев на экране меньше двух — нечего сверять (гонка sr1 обязана показать таймер и круги)'); ok = False
for i in range(len(ov)):
    for j in range(i + 1, len(ov)):
        a, b = ov[i], ov[j]
        if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
            print(f'НАЛОЖЕНИЕ: {names.get(a[0], a[0])} и {names.get(b[0], b[0])}'); ok = False
for l in fit:
    if ' over ' in l: print('  ', l)
if not tot:
    print('нет проверки текстов (UIFIT)'); ok = False
else:
    t, o = tot[-1]; print(f'тексты в рамке задания: влезают {t - o} из {t}'); ok = ok and o == 0
print(f'смоук (FPS/кадры/память): {"OK" if rc == 0 else "ПРОВАЛ"}')
sys.exit(0 if ok and rc == 0 else 1)

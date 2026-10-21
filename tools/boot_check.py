#!/usr/bin/env python3
"""Разбор прогона заставки GONE Makers в эмуляторе (tools/boot_gate.sh): smoke.txt движка + снимки окна кадров появления.
  python tools/boot_check.py OUTDIR       код выхода 0 = OK, 1 = FAIL (первая строка — причина)
Проверки:
  звук — в smoke.txt строка BOOTSND (правка 128: кнопка, кулер, бип POST потоком): канал получен (ch >= 0), отдана вся
         партитура out = n (или остановлена START, stop = 1), rc >= 0, канал освобождён (done = 1), бип 1000..2000 Гц;
  ход  — строка BOOTSEQ: пройдено frames = len кадров (без пропуска START);
  первый кадр (правка Роба 28) — строка BOOTT: от входа в main до первого кадра заставки ≤ FIRST_MS мс;
  кадры появления — снимки boot_f020, boot_f050, boot_f080, boot_f<конец первого прохода>, boot_f<второй проход>, boot_end:
         все есть, не чёрные, и знак меняется между кадрами (появление идёт, а не стоит на месте)."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image

out = Path(sys.argv[1]); fails, lines = [], []
log = (out / 'smoke.txt').read_text(errors='replace') if (out / 'smoke.txt').exists() else ''
kv = lambda tag: dict(re.findall(r'(\w+)=(-?\d+)', next((l for l in log.splitlines() if l.startswith(tag + ' ')), '')))
b, s, bt, bm = kv('BOOTSND'), kv('BOOTSEQ'), kv('BOOTT'), kv('BOOTMARKS')
FIRST_MS = 50
lines.append('BOOTSND ' + ' '.join(f'{k}={v}' for k, v in b.items()) if b else 'BOOTSND: строки нет')
lines.append('BOOTSEQ ' + ' '.join(f'{k}={v}' for k, v in s.items()) if s else 'BOOTSEQ: строки нет')
if not b:
    fails.append('звук: в smoke.txt нет строки BOOTSND')
else:
    if int(b['ch']) < 0: fails.append(f'звук: канала нет (ch={b["ch"]})')
    if (int(b['out']) != int(b['n']) and not int(b['stop'])) or int(b['rc']) < 0:
        fails.append(f'звук не отдан целиком (out={b["out"]} из n={b["n"]}, stop={b["stop"]}, rc={b["rc"]})')
    if not int(b['done']): fails.append('звук: канал не освобождён к концу заставки (done=0)')
    if not 1000 <= int(b['hz']) <= 2000: fails.append(f'бип: частота {b["hz"]} Гц вне 1–2 кГц')
lines.append('BOOTMARKS ' + ' '.join(f'{k}={v}' for k, v in bm.items()) if bm else 'BOOTMARKS: строки нет')
if bm and int(bm['n']) < 0: fails.append('знаки (правка 127): bootmarks.bin рядом с EBOOT испорчен (n=-1)')
lines.append('BOOTT ' + ' '.join(f'{k}={v}' for k, v in bt.items()) if bt else 'BOOTT: строки нет')
if not bt:
    fails.append('первый кадр: в smoke.txt нет строки BOOTT')
elif int(bt['first_ms']) > FIRST_MS:
    fails.append(f'первый кадр заставки через {bt["first_ms"]} мс после входа в main (> {FIRST_MS}) — правка Роба 28')
if not s:
    fails.append('ход: в smoke.txt нет строки BOOTSEQ')
elif int(s['frames']) != int(s['len']) or int(s['skip']):
    fails.append(f'ход: пройдено {s["frames"]} из {s["len"]} кадров (skip={s["skip"]})')
shots = sorted(out.glob('boot_*.png'), key=lambda p: (p.stem == 'boot_end', p.stem))   # по времени: f020 … boot_end
lines.append('снимки: ' + (', '.join(p.stem for p in shots) or 'нет'))
if len(shots) < 6:
    fails.append(f'кадры появления: снимков {len(shots)} из 6')
else:
    ims = [np.asarray(Image.open(p).convert('L').resize((480, 272))).astype(int) for p in shots]
    for p, im in zip(shots, ims):
        if (im > 40).mean() < .002: fails.append(f'кадр {p.stem} чёрный')
    # правый верхний угол (знак): соседние кадры появления различаются, конец = после второго прохода
    logo = [im[:80, 300:] for im in ims]
    diffs = [float(np.abs(logo[i] - logo[i + 1]).mean()) for i in range(len(logo) - 1)]
    lines.append('изменение знака между кадрами: ' + ' '.join(f'{d:.1f}' for d in diffs))
    # знак проявляется после строк проверки железа (кадры до этого — без знака): сравниваем только кадры, где знак уже есть
    lit = [i for i, lg in enumerate(logo) if (lg[18:] > 90).mean() > .01]   # без полосы заголовка окна (снимок окна эмулятора)
    lines.append('кадры со знаком: ' + ', '.join(shots[i].stem for i in lit))
    live = [float(np.abs(logo[a] - logo[b]).mean()) for a, b in zip(lit, lit[1:])]
    if bm and int(bm['n']) > 0:   # правка 127: знаки причастных под проверками (слоты y 160–248) на итоговом кадре
        zone = ims[-1][150:260, :]
        lines.append(f'знаки: горящих в зоне слотов {100 * (zone > 60).mean():.1f}%')
        if (zone > 60).mean() < .01: fails.append('знаки (правка 127): зона слотов на итоговом кадре пустая')
    if len(lit) < 3: fails.append(f'кадры появления: знак виден только на {len(lit)} снимках из {len(shots)}')
    elif min(live) < .5: fails.append('кадры появления: знак не меняется между кадрами')
if fails:
    print('FAIL: ' + fails[0]); print('\n'.join(lines)); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
print('OK: звук включения сыгран, ход заставки пройден, кадры появления сняты'); print('\n'.join(lines))

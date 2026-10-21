#!/usr/bin/env python3
# №791: сводка прогона эмулятора по сценам: строки CAMV (пол/стена в ближней плоскости, под землёй, полоса GE, подъём бампера),
# цена кадра RFAST work_ms, доля среза на CPU GGSTAT ggOn, точный отброс GE DIAGS (city, listdrop). camv_sum.py ПРОГОН [ПРОГОН …]
# CAMV печатается при следующем «flag camin»: в cam_base.txt — в начале следующей сцены (окно предыдущей), в сценариях a331 — в конце своей
import sys, os, re
RUNS = os.path.expanduser('~/Downloads/shar-psp-render-w/build/emu_runs')
def kv(line):
    return dict(m.groups() for m in re.finditer(r'(\w+)=([-\d.]+)', line))
for run in sys.argv[1:]:
    p = run if os.path.isfile(run) else os.path.join(RUNS, run, 'smoke.txt')
    sc, S, camv = '-', {}, []
    for line in open(p, encoding='utf-8', errors='replace'):
        if line.startswith('SCENE '): sc = line.split()[1]; continue
        d = S.setdefault(sc, {'w': 0., 'n': 0, 'f': 0, 'on': 0, 'drop': 0, 'city': 0, 'cdrop': 0})
        if line.startswith('CAMV '):
            k = kv(line)
            if int(k.get('frames', 0)) >= 50: camv.append((sc, k))
        elif line.startswith('RFAST'):
            k = kv(line)
            if 'work_ms' in k: d['w'] += float(k['work_ms']); d['n'] += 1
        elif line.startswith('GGSTAT'):
            k = kv(line); d['f'] += int(k.get('frames', 0)); d['on'] += int(k.get('ggOn', 0))
        elif line.startswith('DIAGS'):
            k = kv(line); d['drop'] += int(k.get('listdrop', 0)); d['city'] += int(k.get('city', 0)); d['cdrop'] += int(k.get('citydrop', 0))
    print('==', run)
    for s, k in camv:
        print('  CAMV в сцене %-12s кадров %4s пол %3s стена %3s мир %3s подземлёй %3s полосаGE %3s бампер %s/%s м, %s мкс/кадр' % (
            s, k.get('frames'), k.get('vfloor'), k.get('vwall'), k.get('near'), k.get('ground'), k.get('gband'), k.get('blift', '-'), k.get('bliftmax', '-'), k.get('bump_us', '-')))
    for s, d in S.items():
        if d['n'] and s not in ('-', 'start', 'CAM_END'):
            print('  %-12s work %.2f мс  ggOn %.3f  риск GE: город %d (точно выброшено %d), листы выброшено %d' % (s, d['w'] / d['n'], d['on'] / d['f'] if d['f'] else 0., d['city'], d['cdrop'], d['drop']))

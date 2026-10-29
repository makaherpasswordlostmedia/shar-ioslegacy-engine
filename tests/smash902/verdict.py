#!/usr/bin/env python3
"""№902 вердикт: построчное сравнение заездов «новое» против «прежнее» (SP_WALL902_OLD=1) по ключу (предмет, направление, смещение, скорость).
Класс результата: 0 в кадр удара (0–1 кадр от подхода в 35 см), 1 — 2–6 кадров, 2 — 7 и позже, 3 — без события за 1,5 с.
python verdict.py NEW1.txt OLD1.txt [NEW2.txt OLD2.txt ...]    (файлы — вывод host с аргументом cases; пары по уровням)
PASS: ни один заезд не стал хуже (класс не вырос), хотя бы один лучше, «без события» не больше прежнего, «в кадр удара» не меньше прежнего.
Рост счётчика «7+» сам по себе не вред: туда переезжают заезды, которые раньше не били вовсе (класс 3 -> 2)."""
import sys, collections
def rd(p): return {tuple(l.split()[1:5]): int(l.split()[5]) for l in open(p) if l.startswith('CASE')}
def cls(r): return 3 if r == -2 else 0 if r <= 1 else 1 if r < 7 else 2
tot = collections.Counter(); worse = []
args = sys.argv[1:]
for i in range(0, len(args), 2):
    n, o = rd(args[i]), rd(args[i + 1]); lv = i // 2 + 1
    for k in n:
        if k not in o or n[k] == -1 or o[k] == -1: continue
        a, b = cls(o[k]), cls(n[k])
        tot['new%d' % b] += 1; tot['old%d' % a] += 1
        if b > a: worse.append((lv, k, o[k], n[k]))
        elif b < a: tot['better'] += 1
        elif n[k] < o[k] and a == 1: tot['better'] += 1
print('в кадр удара: прежнее %d -> новое %d; 2–6 кадров: %d -> %d; 7+: %d -> %d; без события: %d -> %d' % (tot['old0'], tot['new0'], tot['old1'], tot['new1'], tot['old2'], tot['new2'], tot['old3'], tot['new3']))
print('заездов лучше: %d, хуже: %d' % (tot['better'], len(worse)))
for w in worse[:10]: print('  хуже: L%d заезд %s было %d стало %d' % w)
ok = not worse and tot['better'] > 0 and tot['new3'] <= tot['old3'] and tot['new0'] >= tot['old0']
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)

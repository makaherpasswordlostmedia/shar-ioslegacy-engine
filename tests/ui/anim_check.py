#!/usr/bin/env python3
"""Сверка гейта анимаций HUD по smoke.txt эмулятора (tools/ui_anim_gate.sh, сценарий tests/ui/anim_scenario.txt).
   anim_check.py SMOKE_TXT -> код 0 = всё зелёное; печатает по разделу OK / КРАСНОЕ и строки проверок.
Замер — то, что ушло в GE: рамка △ (UIPULSE), последняя вершина веера кольца и её цвет (UIHNR), нарисованная рамка
группы уведомления и её альфа (UIPOP), номер голоса звука (UISFX)."""
import math
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import anim_rules as R  # noqa: E402

log = open(sys.argv[1], encoding='utf-8', errors='replace').read().splitlines()


def kv(line):
    return dict(m.groups() for m in re.finditer(r'(\w+)=(\S+)', line))


def runs(rows, key):
    """разбить по перезапуску возраста (age уменьшился) -> список серий"""
    out, cur, last = [], [], None
    for r in rows:
        a = key(r)
        if last is not None and a < last - 1e-4:
            out.append(cur); cur = []
        cur.append(r); last = a
    if cur:
        out.append(cur)
    return out


results = []
# ---- пульс △: масштаб = ширина нарисованной рамки / ширина картинки, центр неподвижен
P = [kv(l) for l in log if l.startswith('UIPULSE ')]
pr = runs(P, lambda d: float(d['age']))
if pr:
    s = [(float(d['age']), (float(d['x1']) - float(d['x0'])) / float(d['w0'])) for d in pr[0]]
    cx = [(float(d['x0']) + float(d['x1'])) / 2 for d in pr[0]]; cy = [(float(d['y0']) + float(d['y1'])) / 2 for d in pr[0]]
    chk = R.pulse(s)
    chk.append((max(cx) - min(cx) <= 0.6 and max(cy) - min(cy) <= 0.6,
                'масштаб от центра: центр гуляет на %.2f x %.2f px (<= 0.6)' % (max(cx) - min(cx), max(cy) - min(cy))))
    chk.append((True, 'кадров %d, масштаб %.3f..%.3f' % (len(s), min(v for _, v in s), max(v for _, v in s))))
else:
    chk = [(False, 'нет строк UIPULSE (△ не рисовался)')]
results.append(R.report('пульс △ (эмулятор)', chk))

# ---- кольцо Hit & Run: доля круга по последней вершине веера = показ; цвет — как ушёл в GE
H = [kv(l) for l in log if l.startswith('UIHNR ')]
A0, SPAN = math.radians(21.3), math.radians(313.0)   # дуга оригинала (viewer/ui_radial.h, правка 241): 0 — 21.3°, 100 — 334.3°
rows, drift = [], 0.0
for d in H:
    sh = int(d['shown']); u, v = map(float, d['end'].split(','))
    frac = (((math.atan2(v - .5, u - .5) + math.pi / 2 - A0) % (2 * math.pi)) / SPAN)
    drift = max(drift, abs(frac * 1000 - sh))
    rows.append((float(d['te']), int(d['target']), sh, int(d['light']), int(d['col'], 16), int(d.get('pursuit', 0))))
chk = R.hnr(rows) if rows else [(False, 'нет строк UIHNR (кольцо не рисовалось)')]
if rows:
    chk.append((drift <= 16, 'нарисовано = показ: расхождение веера %.1f/1000 (<= 16)' % drift))
results.append(R.report('кольцо Hit & Run (эмулятор)', chk))

# ---- всплывание: тег 19 STAGE COMPLETE, 20 MISSION COMPLETE (надписи), 5 рамка задания
Q = [kv(l) for l in log if l.startswith('UIPOP ')]
for tag, kind, name in ((19, 0, 'STAGE COMPLETE'), (20, 0, 'MISSION COMPLETE'), (5, 1, 'рамка задания')):
    q = [d for d in Q if int(d['tag']) == tag]
    on = [d for d in q if d['on'] == '1']; off = [d for d in q if d['on'] == '0']
    if not on:
        results.append(R.report('всплывание %s (эмулятор)' % name, [(False, 'нет строк UIPOP tag=%d' % tag)])); continue
    ron = runs(on, lambda d: float(d['age']))
    steady = [float(d['w']) for d in on if float(d['age']) > .5] or [float(on[-1]['w'])]
    w1 = statistics.median(steady)
    chk = R.pop_in([(float(d['age']), float(d['w']) / w1, float(d['a'])) for d in ron[0]], kind)
    roff = runs(off, lambda d: float(d['age']))
    chk += R.pop_out([(float(d['age']), float(d['a'])) for d in roff[0]] if roff else [])
    if tag == 5:
        chk.append((len(ron) >= 2, 'новый текст задания всплыл заново: серий %d (>= 2)' % len(ron)))
    results.append(R.report('всплывание %s (эмулятор)' % name, chk))

# ---- звуки интерфейса: событие -> ресурс диска, голос выдан
S = [kv(l) for l in log if l.startswith('UISFX ')]
need = [('stage_complete', 1), ('mission_complete', 1), ('pop_up', 2), ('pause_on', 1), ('scroll', 1), ('pause_off', 1)]
chk = []
for nm, n in need:
    got = [d for d in S if d['name'] == nm]
    good = [d for d in got if int(d['id']) >= 0 and int(d['h']) >= 0]
    chk.append((len(good) >= n, '%s: сыграно %d из %d (строк %d%s)' % (nm, len(good), n, len(got),
                ', id %s h %s' % (got[0]['id'], got[0]['h']) if got else '')))
results.append(R.report('звуки интерфейса (эмулятор)', chk))

ok = all(r[0] for r in results)
print('anim emu: OK' if ok else 'anim emu: КРАСНОЕ')
for _, t in results:
    print(t)
sys.exit(0 if ok else 1)

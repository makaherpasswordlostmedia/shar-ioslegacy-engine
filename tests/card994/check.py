#!/usr/bin/env python3
"""№994 гейт: карточка миссии перед миссией — первый видимый кадр карточки уже в руке за краем экрана, въезд без отката назад.
Читает BRIEFANIM / BRIEFDRAW из smoke.txt (flag brtrace; сценарий brief_scenario.txt: три брифинга, первый на уровне — с газетой).
  check.py enter DIR   код выхода 0 — PASS"""
import re, sys
from pathlib import Path

ANIM = re.compile(r'BRIEFANIM on=(\d) us=(\d+)')
DRAW = re.compile(r'BRIEFDRAW us=(\d+)(?: wait=(\d))? anim=(\d) on=(\d) leaving=(\d) dx=(\S+) armL=(\S+) armR=(\S+) showL=(\d) showR=(\d)')

def enter(d):
    ev = []
    for l in (Path(d) / 'smoke.txt').read_text().splitlines():
        m = ANIM.match(l)
        if m: ev.append(('A', int(m[1]), int(m[2]))); continue
        m = DRAW.match(l)
        if m: ev.append(('D', int(m[1]), dict(wait=int(m[2] or 0), anim=int(m[3]), lv=int(m[5]), dx=float(m[6]), sL=int(m[9]))))
    seqs = []; cur = None
    for e in ev:
        if e[0] == 'A' and e[1] == 1 and (cur is None or cur['closed']): cur = dict(rows=[], closed=False); seqs.append(cur)
        elif e[0] == 'A' and e[1] == 0 and cur: cur['closed'] = True
        elif e[0] == 'D' and cur and not cur['closed'] and e[2]['lv'] == 0: cur['rows'].append((e[1], e[2]))
    if len(seqs) < 3: return f'FAIL: найдено {len(seqs)} брифингов из 3'
    bad = []; info = []
    for k, s in enumerate(seqs[:3]):
        vis = [(t, r) for t, r in s['rows'] if r['wait'] == 0 and r['anim'] == 1]   # кадры, где карточка рисуется
        if not vis: bad.append(f'#{k}: карточка ни разу не нарисована'); continue
        t0, r0 = vis[0]
        if r0['dx'] > -300: bad.append(f'#{k}: первый видимый кадр карточки на dx={r0["dx"]:.0f} (нужно за краем, ≤ -300): карточка показана на месте до въезда')
        if r0['sL'] != 1: bad.append(f'#{k}: в первом кадре нет руки')
        back = max((vis[i][1]['dx'] - vis[i + 1][1]['dx'] for i in range(len(vis) - 1)), default=0)
        if back > 5: bad.append(f'#{k}: карточка откатилась назад на {back:.0f} px (повторный запуск въезда)')
        arrive = next((t for t, r in vis if r['dx'] >= -1.0), None)
        dur = (arrive - t0) / 1e6 if arrive else 9
        if not (0.30 <= dur <= 0.55): bad.append(f'#{k}: въезд {dur:.2f} с (нужно 0,40 ±0,15)')
        info.append(f'#{k}: первый кадр dx={r0["dx"]:.0f}, въезд {dur:.2f} с, откат {max(back, 0):.0f} px, кадров до въезда на месте {sum(1 for t, r in vis if t < (arrive or 0) and r["dx"] >= -1)}')
    print('  замер:', '; '.join(info))
    return 'PASS' if not bad else 'FAIL: ' + '; '.join(bad)

if __name__ == '__main__':
    r = globals()[sys.argv[1]](sys.argv[2]); print(r); sys.exit(0 if r == 'PASS' else 1)

#!/usr/bin/env python3
"""Итог прогона tests/rooms/emu_cams_lN.txt: по каждой камере комнат CAMIN eye (глаз внутри ящика куска) / near (ближе 0,3 м), nearmin, HOMER room=/cam= (какая камера выбрана).
  .venv/bin/python tests/rooms/emu_cams_levels_report.py build/smoke/<время>/smoke.txt"""
import re, sys
rows = open(sys.argv[1], errors='replace').read().splitlines()
scene = None; res = {}; order = []
for l in rows:
    m = re.match(r'SCENE (\S+)', l)
    if m: scene = m.group(1); res.setdefault(scene, {'camin': [], 'room': '-', 'cam': '-', 'lvl': '-'}); order.append(scene) if scene not in order else None; continue
    if not scene: continue
    m = re.match(r'CAMIN t=\S+ frames=(\d+) any=(\d+) eye=(\d+) near=(\d+) .*?nearmin=([\d.]+)', l)
    if m: res[scene]['camin'].append(tuple(float(x) for x in m.groups()))
    m = re.search(r'HOMER t=\S+ pos=\S+ h=\S+ room=(\S+) cam=(\S+)', l)
    if m: res[scene]['room'], res[scene]['cam'] = m.group(1), m.group(2)
    m = re.match(r'BB\s+\d+\s+\S+\s+(L\d)', l)
    if m: res[scene]['lvl'] = m.group(1)
bad = tot = 0
for s in order:
    r = res[s]
    if not r['camin']: continue
    fr, anyf, eye, near, nm = r['camin'][-1]
    if r['room'] == '-' and not s.endswith('_door') and len(r['camin']) < 2: continue
    tot += 1; flag = ' <<< ГЛАЗ В СТЕНЕ' if eye > 0 else (' <- ближе 0,3 м' if near > 0 else '')
    if eye > 0: bad += 1
    print(f"{r['lvl']} {s:14s} room={r['room']:22s} cam={r['cam']:22s} кадров={int(fr):3d} eye={int(eye)} near={int(near)} nearmin={nm:.2f}{flag}")
print(f'итог: точек {tot}, с глазом внутри куска {bad}')

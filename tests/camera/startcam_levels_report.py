#!/usr/bin/env python3
"""Итог свипа камер старта миссий уровня N в режиме игрока: smoke.txt прогона tests/camera/startcam_lN.txt сверяется с камерами из данных (tools/msncam_export.cameras).
  .venv/bin/python tests/camera/startcam_levels_report.py N build/smoke/<время>/smoke.txt"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
import msncam_export as M
n = int(sys.argv[1]); rows = open(sys.argv[2], errors='replace').read().splitlines()
data = {ph.lower(): cam for m, script, cam, p3d, ph in M.cameras(n)}
sel, cur, res = [], None, {}
scene = None
for l in rows:
    m = re.match(r'SCENE (\S+)', l)
    if m: scene = m.group(1)
    m = re.match(r'MSN select (\S+)', l)
    if m: cur = m.group(1); sel.append(cur); res[cur] = {'scene': scene, 'req': 0, 'play': 0, 'end': 0, 'skip': 0, 'frames': 0}
    if cur and re.match(r'MSNCAM req', l) and 'play=1' in l: res[cur]['req'] += 1
    if cur and l.startswith('MSNCAM start'):
        res[cur]['play'] += 1; mm = re.search(r'frames=(\d+)', l); res[cur]['frames'] = int(mm.group(1)) if mm else 0
    if cur and l.startswith('MSNCAM end'): res[cur]['end'] += 1
    if cur and l.startswith('MSNCAM skip'): res[cur]['skip'] += 1
bad = 0
for s in sel:
    r = res[s]; ph = s + 'sd'; has = ph in data or s in data
    ok = (r['play'] >= 1) if has else True
    note = 'камера из данных есть и сыграла' if has and ok else ('камера из данных есть, НЕ сыграла' if has else 'камеры старта в данных нет')
    if not ok: bad += 1
    print(f"L{n} {s:4s} сцена {r['scene']:10s} кадров={r['frames']:4d} конец={r['end']} пропуск={r['skip']}  {note}")
print(f"итог L{n}: миссий {len(sel)}, в данных с камерой {sum(1 for s in sel if s+'sd' in data or s in data)}, не сыграли {bad}")

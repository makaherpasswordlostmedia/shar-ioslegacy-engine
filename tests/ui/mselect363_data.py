#!/usr/bin/env python3
"""Compare the live disc/Scrooby exporter with actual UIP1, then apply fix363 criteria.
UI_MS_348=1 selects genuine pre363 source; the same acceptance contract must fail.
No package export, gameplay mutation, or emulator launch.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests/ui')]
import menu_export as M
import ui_export as U
import ui_typo as UT
import msel_348 as T
T.FIELD_MS0 = U.FIELDS.index('MS0'); T.FIELD_RARROW = U.FIELDS.index('MS_RARROW')
assets = U.Assets(); fonts = U.FontCache('psp')
dl = M.build('missionselect', assets, fonts); cfg = UT.load()
if cfg: dl = UT.apply('missionselect', dl, assets, fonts, cfg)
by = {t['name']: t for t in dl}
its, pf = T.pak(sys.argv[1]); names, nums, icons, bars = T.rows_of(its)
bad = []; coord_count = 0; title_count = 0
for prefix, packed in [('Mission', names), ('MissionNum', nums), ('MissionStatus', icons), ('HighlightBar', sorted(bars,key=lambda t:t['menu']))]:
    if len(packed) != 7: bad.append('%s missing seven items' % prefix); continue
    for k,t in enumerate(packed):
        s = by[prefix+str(k)]
        want = tuple(int(round(v)) for v in s['dst'])
        got = tuple(t[x] for x in ('x','y','w','h'))
        if got != want: bad.append('%s%d packed %s != source %s' % (prefix,k,got,want))
        coord_count += 1
        if prefix == 'Mission':
            if t['strings'] != s['strings']: bad.append('row%d titles differ from source' % k)
            if pf[t['font']]['name'] != s['font']: bad.append('row%d font differs from source' % k)
            title_count += len(t['strings'])
# Source geometry and packed parity are distinct evidence; OLD stays OLD.
rows = [by['Mission%d'%k] for k in range(7)]
numbers = [by['MissionNum%d'%k] for k in range(7)]
lefts = [int(t['dst'][0] + U.glyph_ink(t['font'],t['strings'][0])[0]) for t in numbers]
if len(set(lefts)) != 1: bad.append('363 number ink lefts differ: %s' % lefts)
pitch = rows[1]['dst'][1] - rows[0]['dst'][1]; lh = fonts.get(rows[0]['font'])['lh']
if pitch < 1.5*lh: bad.append('363 tight pitch %s/lh%s' % (pitch,lh))
if any(r['dst'][1] != n['dst'][1] for r,n in zip(rows,numbers)): bad.append('363 number/name baselines differ')
fx,fy,fw,fh = by['Frame_Bgd']['dst']; bar = by['LevelBar']; status = by['Status']; level = by['Level']
num_margin = lefts[0] - (fx+1)
sx0,sx1,sy0,sy1 = U.glyph_ink(status['font'],status['strings'][0])
sw = U.face_width(status['font'],status['strings']); sx = status['dst'][0]
if status['halign'] == 'right': sx += status['dst'][2]-sw
elif status['halign'] == 'centre': sx += (status['dst'][2]-sw)//2
status_margin = (fx+fw-2) - (sx+sx1-1)
bar_margin = bar['dst'][1] - fy
for label,v in [('numbers',num_margin),('Status',status_margin),('LevelBar',bar_margin)]:
    if not T.EDGE_MIN <= v <= T.EDGE_MAX: bad.append('363 %s margin %s not 8..14' % (label,v))
_,_,ly0,ly1 = U.glyph_ink(level['font'],level['strings'][0])
lc = level['dst'][1]+(ly0+ly1)/2; face = bar['dst'][1]+bar['dst'][3]*.4
sh = fonts.get(status['font'])['lh']; sy = status['dst'][1]
if status['valign'] == 'bottom': sy += status['dst'][3]-sh
elif status['valign'] == 'centre': sy += (status['dst'][3]-sh)//2
sc = sy+(sy0+sy1)/2
if not -1.5 <= lc-face <= .75: bad.append('363 LEVEL center %.1f face %.1f' % (lc,face))
if abs(sc-lc)>1.5: bad.append('363 Status and LEVEL centers differ')
print('source/UIP1 coords=%d titles=%d ms_overrides=%s' % (coord_count,title_count,[k for k in cfg.get('groups',{}) if k.startswith('ms_')]))
print('source margins=%s/%s/%s ink_lefts=%s pitch=%s/lh%s LEVEL/face=%.1f/%.1f' % (num_margin,status_margin,bar_margin,lefts,pitch,lh,lc,face))
for b in bad: print('FAIL',b)
print(('FAIL' if bad else 'PASS')+' source-packed363 errors='+str(len(bad)))
sys.exit(bool(bad))

#!/usr/bin/env python3
"""Only fix363 native margins/ink/pitch using real UIP1, not the whole348 navigation gate.
Same checker on real pre363 UI_MS_348 packet/screenshot must fail.
"""
import re,sys,struct
import numpy as np
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/ui'))
import ui_export as U
import msel_348 as T
T.FIELD_MS0=U.FIELDS.index('MS0');T.FIELD_RARROW=U.FIELDS.index('MS_RARROW')
# Geometry criteria copied from msel_348.layout_363; only Status ROI is corrected.
def frame_edges(img, its):
    """Search original yellow thresholds inside actual UIP1 frame strips only.
    Broad row150 search mistakes a yellow mission icon for the right frame.
    """
    a = np.asarray(img.convert('RGB')).astype(int)
    strips = [t for t in its if t['type'] == 2 and t['field'] == 0]
    left = next(t for t in strips if t['w'] < 10 and t['h'] > 100 and t['x'] < 240)
    right = next(t for t in strips if t['w'] < 10 and t['h'] > 100 and t['x'] > 240)
    top = next(t for t in strips if t['w'] > 300 and t['h'] < 10 and t['y'] < 90)
    def yellow(p): return (p[..., 0] > 180) & (p[..., 1] > 130) & (p[..., 2] < 120)
    lx = np.where(yellow(a[left['y'] + left['h']//2, left['x']:left['x']+left['w']]))[0]
    rx = np.where(yellow(a[right['y'] + right['h']//2, right['x']:right['x']+right['w']]))[0]
    ty = np.where(yellow(a[top['y']:top['y']+top['h'], top['x']+top['w']//2]))[0]
    if not all(len(v) for v in (lx,rx,ty)): return None,None,None
    return int(left['x']+lx.max()), int(right['x']+rx.min()), int(top['y']+ty.max())


def layout_363_text_roi(img, its, names, nums, fonts, bad, notes):
    """правка 363 (Роб: «номера неровные — 2, 3 вылазят; отступ чуть больше; LEVEL N и Status выше, ближе к верху, свободнее; Status от
    края; LEVEL на планке выше; строки красивее»): по кадру LEVEL 1 и пакету"""
    xl, xr, yt = frame_edges(img, its)
    if None in (xl, xr, yt): bad.append('363: на кадре не найдена жёлтая линия рамки'); return
    lefts = []
    for t in nums:
        q = T.ink_cols(img, t['x'] - 4, t['x'] + 20, t['y'] - 1, t['y'] + fonts[t['font']]['lh'] + 1)
        lefts.append(q[0] if q else None)
    if None in lefts or max(lefts) != min(lefts): bad.append('363: номера не по одному левому краю букв: %s' % lefts)
    elif not T.EDGE_MIN <= lefts[0] - xl - 1 <= T.EDGE_MAX: bad.append('363: от рамки до номеров %d px (ждём %d..%d)' % (lefts[0] - xl - 1, T.EDGE_MIN, T.EDGE_MAX))
    rows = [(t['y'], n['y']) for t, n in zip(names, nums)]
    if any(a_ != b_ for a_, b_ in rows): bad.append('363: номер и название строки не на одной линии букв: %s' % rows)
    st = next((t for t in its if t['type'] == 3 and t['strings'][:1] == ['Status']), None)
    a = np.asarray(img.convert('RGB')).astype(int)
    sq = None
    if st is not None:
        # Actual UIP1 glyph interval, not the background/frame/icon column.
        # Preserve the existing RGB thresholds and 8..14px acceptance limits.
        f = fonts[st['font']]; tw = T.width(f, st['strings'][0])
        dx = 0 if st['halign'] == 0 else (st['w']-tw if st['halign'] == 2 else (st['w']-tw)//2)
        dy = 0 if st['valign'] == 0 else (st['h']-f['lh'] if st['valign'] == 2 else (st['h']-f['lh'])//2)
        pen = st['x'] + dx; spans = []
        for c in st['strings'][0]:
            n = ord(c)
            if f['w'][n]: spans.append((pen + f['left'][n], pen + f['left'][n] + f['w'][n]))
            pen += f['adv'][n] or 0
        x0 = max(xl + 1, min(v[0] for v in spans))
        x1 = min(xr - 1, max(v[1] for v in spans))
        y0 = st['y'] + dy; y1 = y0 + f['lh']
        q = a[y0:y1, x0:x1]; m = (q[..., 0] > 150) & (q[..., 1] > 150) & (q[..., 2] < 120)
        cs = np.where(m.any(0))[0]; rs = np.where(m.any(1))[0]
        if len(cs): sq = (x0 + cs.max(), y0 + rs.min(), y0 + rs.max())
        notes.append('Status actual-glyph ROI x=%d:%d y=%d:%d' % (x0, x1, y0, y1))
    if sq is None: bad.append('363: Status не найден на кадре')
    elif not T.EDGE_MIN <= xr - sq[0] - 1 <= T.EDGE_MAX: bad.append('363: от Status до рамки справа %d px (ждём %d..%d)' % (xr - sq[0] - 1, T.EDGE_MIN, T.EDGE_MAX))
    bar = next((t for t in its if t['type'] == 2 and t['w'] > 100 and 15 <= t['h'] < 40 and t['y'] < 90), None)   # LevelBar
    if bar is None: bad.append('363: нет планки LevelBar'); return
    if not T.EDGE_MIN <= bar['y'] - yt - 1 <= T.EDGE_MAX: bad.append('363: планка LEVEL N на %d px от верхней линии (ждём %d..%d; ближе к верху)' % (bar['y'] - yt - 1, T.EDGE_MIN, T.EDGE_MAX))
    face = bar['y'] + bar['h'] * 0.4                      # [диск] levelbar.png: лицо — 16 строк из 20, центр 8/20
    q = a[bar['y']:bar['y'] + int(bar['h'] * 0.8), bar['x'] + 30:bar['x'] + bar['w'] - 30].max(-1) < 50
    rs = np.where(q.sum(1) > 2)[0]
    if not len(rs): bad.append('363: букв LEVEL N на планке не видно'); return
    cc = bar['y'] + (rs.min() + rs.max() + 1) / 2.0
    if not -1.5 <= cc - face <= 0.75: bad.append('363: LEVEL N на планке — центр букв %.1f при центре лица %.1f (ниже)' % (cc, face))
    if sq is not None and abs((sq[1] + sq[2] + 1) / 2.0 - cc) > 1.5: bad.append('363: Status и LEVEL N не на одной высоте (%.1f и %.1f)' % ((sq[1] + sq[2] + 1) / 2.0, cc))
    if not any(x.startswith('363') for x in bad):
        notes.append('363: номера с x %d (поле %d px), Status до рамки %d px, планка на %d px от верха, LEVEL N по центру лица (%.1f/%.1f)' %
                     (lefts[0], lefts[0] - xl - 1, xr - sq[0] - 1, bar['y'] - yt - 1, cc, face))

run=Path(sys.argv[1]);pak=Path(sys.argv[2]);log=(run/'smoke.txt').read_text();bad=[];notes=[]
if not re.search(r'^END$',log,re.M):bad.append('no END')
if not re.search(r'MSNSEL open[^\n]*level=1',log):bad.append('no real MISSION SELECT open level1')
img=Image.open(run/'ms_l1.png');its,fonts=T.pak(pak)
# T.pak omits alignment; these bytes determine the actual uiText pen in OLD.
b = pak.read_bytes(); h = struct.unpack_from('<4s19Ii3f', b, 0)
first,count = struct.unpack_from('<4I', b, h[7]+16*T.PX_MS)[:2]
for k,t in enumerate(its):
 t['halign'],t['valign'] = b[h[5]+64*(first+k)+5:h[5]+64*(first+k)+7]
names,nums,icons,bars=T.rows_of(its)
if len(names)!=7 or len(nums)!=7:bad.append('missing seven packed mission rows/numbers')
else:
 pitch=names[1]['y']-names[0]['y'];lh=fonts[names[0]['font']]['lh']
 if pitch<1.5*lh:bad.append('row pitch too tight: %s/%s'%(pitch,lh))
 T.ROWS_ICONS[:] = icons
 # Ordinary checkpoint: first three missions are unlocked, future labels are DIM.
 # All seven row/number geometries are measured below; all 49 titles are packed-data checks.
 T.check_names(img,names[:3],nums[:3],fonts,0,bad,'LEVEL 1 unlocked')
 layout_363_text_roi(img,its,names,nums,fonts,bad,notes)
 notes.append('actual packed pitch=%d font_lh=%d; faces=%s'%(pitch,lh,sorted({fonts[t['font']]['name'] for t in names+nums})))
for n in notes:print(n)
for n in bad:print('FAIL',n)
print(('FAIL' if bad else 'PASS')+' native363 errors='+str(len(bad)))
sys.exit(bool(bad))

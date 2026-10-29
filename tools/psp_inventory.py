import sys, re, json, struct
from pathlib import Path
from collections import defaultdict
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import decompress, chunks, walk
GAME = ROOT / 'hit-and-run-web/source/game'
CAP = 128
def level_of(rel):
    m = re.search(r'(?:^|[/_])l(\d)', rel.lower())
    return f'L{m.group(1)}' if m else 'common'
def psp_bytes(w, h, bpp):
    s = min(1, CAP / max(w, h)); w2, h2 = max(1, int(w*s)), max(1, int(h*s))
    b = bpp if bpp in (4, 8) else 16
    return w2*h2*b//8 + (64 if bpp == 4 else 1024 if bpp == 8 else 0)
per = defaultdict(lambda: dict(files=0, p3d=0, tex=0, ps2=0, psp=0)); hist = defaultdict(int); big = []; err = []
for path in sorted(GAME.rglob('*.p3d')):
    rel = str(path.relative_to(GAME)); lv = per[level_of(rel)]
    try:
        raw = decompress(path.read_bytes()); lv['files'] += 1; lv['p3d'] += len(raw)
        for top in chunks(raw):
            for c in walk(top):
                if c.id != 0x19002 or c.data[4:8] != b'P3DI': continue
                fmt, w, h, bpp, ps, px = struct.unpack_from('<6I', c.data, 8)
                lv['tex'] += 1; lv['ps2'] += ps+px; lv['psp'] += psp_bytes(w, h, bpp); hist[bpp] += 1
                big.append((ps+px, w, h, bpp, rel))
    except Exception as e: err.append(f'{rel}: {e}')
mb = lambda b: f'{b/2**20:7.2f} MB'
print(f"{'group':8} {'files':>6} {'P3D':>10} {'tex':>6} {'tex PS2':>10} {'tex PSP':>10}")
for k in sorted(per):
    v = per[k]; print(f"{k:8} {v['files']:6} {mb(v['p3d'])} {v['tex']:6} {mb(v['ps2'])} {mb(v['psp'])}")
print('\nbpp:', dict(sorted(hist.items())))
print('\nheaviest:')
for s, w, h, bpp, rel in sorted(big, reverse=True)[:10]: print(f'  {s/1024:6.0f} KB {w}x{h} {bpp}bpp {rel}')
if err: print(f'\nerrors: {len(err)}', *err[:5], sep='\n  ')
(ROOT/'inventory.json').write_text(json.dumps(dict(groups=per, bpp=hist, heaviest=sorted(big, reverse=True)[:100], errors=err), indent=1))

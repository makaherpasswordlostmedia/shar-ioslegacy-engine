import sys, re, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import decompress, chunks, walk
LV = sys.argv[1] if len(sys.argv) > 1 else '1'
ART = ROOT / 'hit-and-run-web/source/game/art'
KIND = {'z': 'zone', 'r': 'road', 'i': 'interior', 't': 'terrain'}
rows = []
for p in sorted(ART.glob(f'l{LV}*.p3d')):
    raw = decompress(p.read_bytes()); tex = meshes = 0
    for top in chunks(raw):
        for c in walk(top):
            if c.id == 0x19002 and c.data[4:8] == b'P3DI':
                ps, px = struct.unpack_from('<2I', c.data, 24); tex += ps + px
            elif c.id == 0x10000: meshes += 1
    m = re.match(rf'l{LV}([a-z])', p.stem); kind = KIND.get(m.group(1), m.group(1)) if m else 'other'
    rows.append((len(raw), tex, meshes, kind, p.name))
mb = lambda b: f'{b/2**20:6.2f} MB'
print(f"Level {LV}\n{'file':14} {'kind':9} {'total':>9} {'geometry':>9} {'textures':>9} {'meshes':>6}")
for tot, tex, me, kind, name in sorted(rows, reverse=True):
    print(f'{name:14} {kind:9} {mb(tot)} {mb(tot-tex)} {mb(tex)} {me:6}')
zones = sorted((r for r in rows if r[3] == 'zone'), reverse=True)
if len(zones) >= 2:
    pair = zones[0][0] + zones[1][0]
    print(f'\nheaviest zone: {zones[0][4]} {mb(zones[0][0])}')
    print(f'two heaviest zones together: {mb(pair)}')
    print('fits PSP Slim (~40 MB free for level)' if pair < 40*2**20 else 'too big, geometry must be simplified')

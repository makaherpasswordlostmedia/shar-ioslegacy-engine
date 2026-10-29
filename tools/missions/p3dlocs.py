"""Locators (Pure3D chunk 0x3000005) and their trigger volumes (0x3000006) from level p3d files.

Layout (per donut P3D spec, GPL): Locator2 = lpstring name, u32 type, u32 dataLen, u32 data[dataLen],
f32 pos[3], u32 nTriggers; children: TriggerVolume = lpstring name, u32 isRect, f32 half[3],
f32 m[16] (row-major, rows = local axes, row 3 = translation); LocatorMatrix 0x300000C (64 bytes).
Locator types: 0 Event, 1 Script, 2 Location, 3 CarStart (data[0] = heading, radians), 4 Spline,
5 ZoneEvent, 6 Occlusion, 7 Interior (data = interior name), 8 Directional, 9 ActionEvent,
10 FOV, 11 ?, 12 StaticCam, 13 PedGroup, 14 Coin, 15 SpawnPoint.

Coordinates are converted to the engine convention (hit-and-run-web / level.shr): z mirrored.
"""
import math, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string  # MIT, bounds-checked Pure3D reader

TYPE_NAMES = ['event','script','location','carstart','spline','zone','occlusion','interior','directional',
              'action','fov','type11','staticcam','pedgroup','coin','spawnpoint']

class Locator:
    __slots__ = ('name','type','pos','heading','data','triggers','file','mat')
    def __repr__(self):
        return f'<{self.name} {TYPE_NAMES[self.type] if self.type < 16 else self.type} {self.pos} {self.file}>'

def _mirror(v):
    return (v[0], v[1], -v[2])

def read_locators(path, rel):
    out = []
    try:
        root = read(path)
    except Exception as e:  # corrupt / not a p3d
        return out, f'{rel}: {e}'
    for c in walk(root):
        if c.id != 0x3000005:
            continue
        name, p = string(c.data)
        kind, length = struct.unpack_from('<II', c.data, p)
        payload = c.data[p + 8: p + 8 + length * 4]
        pos = struct.unpack_from('<3f', c.data, p + 8 + length * 4)
        L = Locator()
        L.name = name; L.type = kind; L.pos = _mirror(pos); L.file = rel; L.heading = None; L.data = 0
        if kind == 3 and len(payload) >= 4:
            L.heading = -struct.unpack_from('<f', payload)[0]
        elif kind == 7:
            L.data = payload.split(b'\0')[0].decode('latin-1')
        elif kind == 0 and len(payload) >= 4:
            L.data = struct.unpack_from('<I', payload)[0]
        L.triggers = []
        L.mat = next((struct.unpack_from('<16f', k.data, 0) for k in c.children if k.id == 0x300000C and len(k.data) >= 64), None)   # LocatorMatrix, оси диска (z не отзеркален)
        for t in c.children:
            if t.id != 0x3000006:
                continue
            _, q = string(t.data)
            is_rect, = struct.unpack_from('<I', t.data, q)
            half = struct.unpack_from('<3f', t.data, q + 4)
            m = struct.unpack_from('<16f', t.data, q + 16)
            axes = []; scaled = []
            for r in range(3):
                ax = _mirror(m[r * 4: r * 4 + 3])
                ln = math.sqrt(sum(a * a for a in ax)) or 1.0
                axes.append(tuple(a / ln for a in ax)); scaled.append(half[r] * ln)
            center = _mirror(m[12:15])
            L.triggers.append((1 if is_rect else 0, center, tuple(scaled), axes))
        out.append(L)
    return out, None

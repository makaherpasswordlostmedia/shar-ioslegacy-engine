#!/usr/bin/env python3
"""Бот-репортёр (№871, Роб 23.10): выгрузка уровня для tools/scout/scout.c — только чтение level.shr.

  python3 tools/scout/dump.py LEVEL.shr OUT.bin [--step 10]

Формат OUT.bin (little-endian):
  'SCT1', u32 ntri, u32 npiece, u32 npoint
  float32 tri[ntri][9]            ближняя версия кусков города (owner 0), мировые координаты
  int32   tri_piece[ntri]
  piece[npiece]: float32 cx, cy, cz, r, int32 tris_near, tris_far, flags   (индекс — номер куска в таблице level.shr)
  float32 point[npoint][3]        точки, где можно стоять: нижний слой сетки высот (земля, не крыши), шаг --step м
"""
import struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shr7read as R


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    step = float(sys.argv[sys.argv.index('--step') + 1]) if '--step' in sys.argv else 10.0
    b = src.read_bytes()
    npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76)
    ox, oz, cs = struct.unpack_from('<3f', b, 56); hw, hh = struct.unpack_from('<II', b, 68)
    t = R.load(src)
    P = t['P'].astype(np.float32); PI = t['PI'].astype(np.int32)
    pieces = np.zeros((npc, 7), np.float32); pint = np.zeros((npc, 3), np.int32)
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        bb = r[:6]; fl, ni, own, nf = r[7], r[9], r[10], r[16]
        c = [(bb[k] + bb[k + 3]) / 2 for k in range(3)]; rad = 0.5 * float(np.linalg.norm(np.subtract(bb[3:], bb[:3])))
        pieces[i, :4] = (*c, rad)
        far = nf // 3 if (fl & (1 << 25)) and nf else ni // 3   # без дальней версии — та же ближняя
        pint[i] = (ni // 3 if own == 0 else 0, far if own == 0 else 0, fl)
    hm = np.frombuffer(b, '<i2', hw * hh * 4, 104).reshape(hh, hw, 4).astype(np.float32)
    hm[hm == -32768] = np.nan
    ground = np.nanmin(hm, axis=2) / 100.0   # нижний слой опоры — земля
    k = max(1, int(round(step / cs)))
    pts = []
    for gz in range(k // 2, hh, k):
        for gx in range(k // 2, hw, k):
            y = ground[gz, gx]
            if np.isfinite(y): pts.append((ox + (gx + .5) * cs, float(y), oz + (gz + .5) * cs))
    pts = np.asarray(pts, np.float32)
    with open(out, 'wb') as f:
        f.write(b'SCT1' + struct.pack('<III', len(P), npc, len(pts)))
        f.write(P.reshape(-1, 9).tobytes()); f.write(PI.tobytes())
        rec = np.zeros(npc, dtype=[('c', '<f4', 4), ('n', '<i4', 3)]); rec['c'] = pieces[:, :4]; rec['n'] = pint
        f.write(rec.tobytes()); f.write(pts.tobytes())
    print(f'{src}: треуг {len(P)}, кусков {npc}, точек {len(pts)} (шаг {k * cs:.1f} м) -> {out}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Проверка секций PV2S хост-рендером: кадр по полному PVS1 против кадра по списку сектора (как выберет движок: курс в пределах ±30° от центра), на случайных позах горячих клеток.
  python3 tools/pvs2_check.py LEVEL_WITH_PV2S.shr [--poses 40] [--cells 12] [--seed 3]   → число различающихся пикселей, максимум и среднее; код 0 при максимуме <= --max-px %"""
import argparse, math, random, struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/autoexplore/tracks')); import hostshot as H
def load_pv2(S):
    b = S.b; off = struct.unpack_from('<I', b, 88)[0]; W, Hh, pool, _ = struct.unpack_from('<4I', b, off + 16); o2 = (off + 32 + W * Hh * 8 + pool * 2 + 15) & ~15
    if b[o2:o2 + 4] != b'PV2S': return None
    nh, ns, npool = struct.unpack_from('<3I', b, o2 + 4); cells = np.frombuffer(b, '<u4', nh, o2 + 32); sec = np.frombuffer(b, '<u4', nh * ns * 2, o2 + 32 + 4 * nh).reshape(nh, ns, 2)
    pl = np.frombuffer(b, '<u2', npool, o2 + 32 + 4 * nh + 8 * nh * ns); return W, cells, sec, pl
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('--poses', type=int, default=40); ap.add_argument('--cells', type=int, default=12); ap.add_argument('--seed', type=int, default=3); ap.add_argument('--max-px', type=float, default=0.05)
    a = ap.parse_args(); S = H.Shooter(a.level); pv = load_pv2(S); rng = random.Random(a.seed)
    if pv is None: print('нет PV2S'); sys.exit(2)
    W, cells, sec, pl = pv; ox, oz, cell = S.pvs[0], S.pvs[1], S.pvs[2]; diffs = []; pick = rng.sample(range(len(cells)), min(a.cells, len(cells)))
    for hi in pick:
        ci = int(cells[hi]); gz, gx = divmod(ci, W)
        for _ in range(max(1, a.poses // len(pick))):
            x = ox + (gx + rng.random()) * cell; z = oz + (gz + rng.random()) * cell; ly = S.hm[int((z - S.hoz) // S.hcell), int((x - S.hox) // S.hcell)]; ly = [v * .01 for v in ly if v != -32768]
            if not ly: continue
            y = rng.choice(ly) + rng.uniform(1.5, 5.8); s = rng.randrange(8); yaw = s * math.pi / 4 + rng.uniform(-math.radians(30), math.radians(30)); pitch = rng.uniform(-0.35, 0.05)
            st, n = sec[hi, s]; lst = pl[st:st + n].astype(np.int64)
            A = S.shot(0, 0, 0, 0, None, '', 'normal', ret_img=True, pose=((x, y, z), yaw, pitch))['img']; B = S.shot(0, 0, 0, 0, None, '', 'normal', ret_img=True, pose=((x, y, z), yaw, pitch), restrict=lst)['img']
            diffs.append(float((np.abs(A.astype(int) - B.astype(int)).max(2) > 0).mean() * 100))
    d = np.array(diffs); print(f'поз {len(d)} в {len(pick)} горячих клетках: различающихся пикселей, %: среднее {d.mean():.4f}, максимум {d.max():.4f}, поз с различием {int((d>0).sum())}')
    sys.exit(0 if d.max() <= a.max_px else 1)
if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Правка 328: маршруты езды для эмулятора (tests/traffic/spawnview_emu.sh) — по полосам трафика уровня (traffic.shr TRF1):
полоса -> перекрёсток -> случайный выезд (без разворота), точки через STEP м, до 32 точек на маршрут (предел wp в viewer/main.c).
   spawnview_route.py traffic.shr [маршрутов] [зерно] > сценарий
Пишет сценарий smoke: на маршрут — goto на первую точку, разгон, wp..., wpgo, ожидание по длине пути."""
import struct, sys, math, random
STEP, NWP, V = 24.0, 32, 17.0
def load(path):
    b = open(path, 'rb').read(); h = struct.unpack_from('<4sIII' + 'I' * 60, b, 0)
    nJ, oJ, nR, oR, nP, oP, nO, oO = h[3:11]
    J = [struct.unpack_from('<ffffIHHHH', b, oJ + 32 * j) for j in range(nJ)]   # x y z r beh firstOut nOut nIn pad
    out = struct.unpack_from('<%dH' % nO, b, oO)
    R = []
    for r in range(nR):
        sj, ej, rev, lanes, flags, maxc, speed, p8, first, npt = struct.unpack_from('<HHHHBBBBIH', b, oR + 32 * r)
        pts = [struct.unpack_from('<ffff', b, oP + 16 * (first + k)) for k in range(npt)]   # полоса 0
        R.append(dict(sj=sj, ej=ej, rev=rev, lanes=lanes, ok=not (flags & 3) and lanes > 0, pts=pts))
    return J, out, R
def route(J, out, R, rng):
    while True:
        r = rng.randrange(len(R))
        if R[r]['ok'] and R[r]['pts'][-1][3] > 60: break
    wps, carry, prev = [], 0.0, None
    for _ in range(40):
        P = R[r]['pts']
        for k in range(len(P) - 1):
            a, b = P[k], P[k + 1]; L = b[3] - a[3]
            s = STEP - carry
            while s <= L:
                u = s / L; wps.append((a[0] + (b[0] - a[0]) * u, a[2] + (b[2] - a[2]) * u)); s += STEP
            carry = L - (s - STEP)
        if len(wps) >= NWP + 1: break
        j = J[R[r]['ej']]; cand = [out[j[5] + i] for i in range(j[6])]
        cand = [o for o in cand if R[o]['ok'] and o != R[r]['rev'] and R[o]['ej'] != R[r]['sj']]
        if not cand: break
        r = rng.choice(cand)
    return wps[:NWP + 1]
if __name__ == '__main__':
    J, out, R = load(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 3; rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 328)
    k = 0
    while k < n:
        w = route(J, out, R, rng)
        if len(w) < 20: continue
        k += 1; h = math.atan2(w[1][0] - w[0][0], w[1][1] - w[0][1])
        print(f'scene drive{k}\nflag wpclear\ngoto {w[0][0]:.1f} {w[0][1]:.1f} {h:.4f}\nwait 3\nflag wpv {V:.0f}')
        for x, z in w[1:]: print(f'flag wp {x:.1f} {z:.1f}')
        print(f'flag wpgo\nwait {len(w) * STEP / V + 6:.0f}\nflag stop\nwait 2')
    print('end')

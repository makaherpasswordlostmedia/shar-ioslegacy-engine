#!/usr/bin/env python3
# №928 приёмка: пересчитать только профили ориентиров в готовом horizon.shr (HOR1) — ячейки и контуры не трогаются (ось, основание и высота те же, что у прежнего экспорта),
# вместо шести минут на уровень — секунды. lm_reprofile.py level.shr horizon_in.shr horizon_out.shr LVL
import sys, json, struct, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import shr7read, horizon_export as he
lv, fin, fout, L = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
d = shr7read.load(lv, far=False, owner=0); keep = (d['FL'] & (1 | 2 | 4)) == 0
V = d['P'][keep].reshape(-1, 3); V = np.concatenate([V, d['P'][keep].mean(1)])
lmj = json.loads((Path(__file__).resolve().parent / 'horizon_landmarks.json').read_text())[str(L)]
b = bytearray(Path(fin).read_bytes()); nl, lo = struct.unpack_from('<II', b, 12); assert nl == len(lmj), (nl, len(lmj))
old = [struct.unpack_from('<4f', b, lo + 32 * i) for i in range(nl)]
lms = []
for (lx, lz, lr), o in zip(lmj, old):
    r = he.extract_landmark(V, lx, lz, lr); assert r and max(abs(r[0] - o[0]), abs(r[1] - o[1]), abs(r[2] - o[2]), abs(r[3] - o[3])) < 0.05, (lx, lz, r[:4], o)
    lms.append(r)
    V = V[~((np.hypot(V[:, 0] - lx, V[:, 2] - lz) < max(lr, 14.)) & (V[:, 1] > (r[2] + 1.0)))]   # как в экспорте: геометрия ориентира вырезается, следующие считаются без неё
lbase = lo + 32 * nl; ltab = bytearray(); lblob = bytearray()
for (cx, cz, y0, H, prof) in lms:
    ltab += struct.pack('<4fII8x', cx, cz, y0, H, len(prof), lbase + len(lblob))
    for (rr, hh) in prof: lblob += struct.pack('<HH', min(65535, int(round(rr * 100))), min(65535, int(round(hh * 100))))
Path(fout).write_bytes(bytes(b[:lo]) + bytes(ltab) + bytes(lblob)); print('ориентиров', nl, 'байт', lbase + len(lblob))

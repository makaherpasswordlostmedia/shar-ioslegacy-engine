#!/usr/bin/env python3
"""Гейт №928 (приёмка «Контур»): ориентиры дали на ВСЕХ семи уровнях — карточка не шире настоящего здания больше чем в 1,5 раза, высота и ось совпадают с геометрией.
Для каждого ориентира horizon.shr берём вершины level.shr в радиусе отбора (как в экспорте, с вырезом ранее взятых ориентиров), на каждой высоте (шаг 2 м) считаем настоящую ширину по 12 азимутам
и сравниваем площадь карточки (профиль вращения, ширина 2·радиус) с настоящей по каждому азимуту. Зелёное: у ≤ 5 % ориентиров медиана по азимутам > 1,5, у ≤ 20 % худший азимут > 1,5,
у ≤ 10 % лучший азимут < 0,6 (карточка не уже), верх карточки не ниже верхушки настоящего (≤ 1 м). Красное: horizon.shr №928 до приёмки (профиль «радиус до дальней вершины») обязан не пройти.
  tests/horizon/lmq928.py НАБОР_каталог(PSP/GAME/SHARTEST15) КАТАЛОГ_horizon_l1..l7.shr [КАТАЛОГ_старых_для_красного]   код 0 = OK"""
import sys, json, struct, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools')); import shr7read
LM = json.loads((ROOT / 'tools/horizon_landmarks.json').read_text())
def read_lms(p):
    b = Path(p).read_bytes(); nl, lo = struct.unpack_from('<II', b, 12); out = []
    for i in range(nl):
        cx, cz, y0, H, n, off = struct.unpack_from('<4fII', b, lo + 32 * i)
        out.append(dict(cx=cx, cz=cz, y0=y0, H=H, prof=[tuple(v / 100. for v in struct.unpack_from('<HH', b, off + 4 * k)) for k in range(n)]))
    return out
def vertices(S, L):
    d = shr7read.load(str(S / ('level.shr' if L == 1 else f'l{L}/level.shr')), far=False, owner=0); keep = (d['FL'] & (1 | 2 | 4)) == 0
    V = d['P'][keep].reshape(-1, 3); return np.concatenate([V, d['P'][keep].mean(1)])
def stats(S, D):
    rows = []
    for L in range(1, 8):
        lms = read_lms(Path(D) / f'l{L}.shr'); V = vertices(S, L)
        for lm, (lx, lz, lr) in zip(lms, LM[str(L)]):
            m = np.hypot(V[:, 0] - lx, V[:, 2] - lz) < lr; W = V[m]; cx, cz, y0, H = lm['cx'], lm['cz'], lm['y0'], lm['H']
            P = np.array(lm['prof']); hs = np.arange(0, H + 1, 2.0); card = np.interp(hs, P[:, 1], P[:, 0]) * 2
            h = W[:, 1] - y0; rel = np.stack([W[:, 0] - cx, W[:, 2] - cz], 1); rr = []
            for az in np.arange(0, 180, 15):
                a = np.radians(az); pr = rel @ np.array([np.cos(a), -np.sin(a)]); wid = np.array([(pr[(h >= hh - 1) & (h < hh + 1)].max() - pr[(h >= hh - 1) & (h < hh + 1)].min()) if ((h >= hh - 1) & (h < hh + 1)).sum() >= 2 else 0. for hh in hs]); ok = wid > 0.3
                rr.append((card * ok).sum() / max(1e-6, (wid * ok).sum()) if ok.any() else np.nan)
            rr = np.array(rr); rows.append(dict(L=L, med=float(np.nanmedian(rr)), mx=float(np.nanmax(rr)), mn=float(np.nanmin(rr)), topd=float(y0 + H - W[:, 1].max())))
            V = V[~((np.hypot(V[:, 0] - lx, V[:, 2] - lz) < max(lr, 14.)) & (V[:, 1] > y0 + 1.0))]
    return rows
def verdict(rows):
    n = len(rows); a = sum(r['med'] > 1.5 for r in rows) / n; b = sum(r['mx'] > 1.5 for r in rows) / n; c = sum(r['mn'] < 0.6 for r in rows) / n; t = sum(r['topd'] < -1.0 for r in rows) / n
    return (a <= .05 and b <= .20 and c <= .10 and t == 0), (n, a, b, c, t)
S = Path(sys.argv[1]); new = stats(S, sys.argv[2]); ok, v = verdict(new)
print('новые: ориентиров %d; медиана азимутов >1,5 у %.0f %%, худший азимут >1,5 у %.0f %%, лучший <0,6 у %.0f %%, верх ниже настоящего у %.0f %%' % (v[0], v[1] * 100, v[2] * 100, v[3] * 100, v[4] * 100))
for L in range(1, 8):
    rs = [r for r in new if r['L'] == L]; print('  L%d: медиана отношения %.2f, >1,5 по худшему азимуту у %d из %d' % (L, np.median([r['med'] for r in rs]), sum(r['mx'] > 1.5 for r in rs), len(rs)))
red_ok = True
if len(sys.argv) > 3:
    okr, vr = verdict(stats(S, sys.argv[3])); red_ok = not okr
    print('красное (прежний профиль): медиана >1,5 у %.0f %%, худший >1,5 у %.0f %% -> %s' % (vr[1] * 100, vr[2] * 100, 'красное как надо' if red_ok else 'ПРОШЛО — проверка слепая'))
print('PASS' if ok and red_ok else 'FAIL'); sys.exit(0 if ok and red_ok else 1)

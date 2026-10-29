#!/usr/bin/env python3
"""Гейт правки Роба 411 (дальний город без дымки, недотекстуренное — тоном горизонта) по прогону tests/fartint/gen.sh.

Прогон:  tests/fartint/run.sh            (сценарий scenario.txt, ждём PASS)
         tests/fartint/run.sh red        (scenario_red.txt — «новые» кадры прежним путём; гейт обязан упасть)
Все сравнения — внутри одного прогона, в одних и тех же видах (пары кадров одного вида), без подобранных порогов:
  Запас каждого сравнения — шум, измеренный в том же прогоне: повтор кадра через 0,4 с (U = T, R = P).
  G1 дымка:    Σ|A−T| + Σ|U−T| < Σ|F−T| по маске M (город дальше 150 м): даль своего цвета, а не цвета тумана
  G2 заглушка: Σ px·|ср.P − H| + Σ px·|ср.R − ср.P| < Σ px·|ср.Q − H|: недотекстуренное ближе к тону горизонта, чем цвет вершин
  G3 тон:      Σ |fogCol(кадра) − H| < Σ |fogCol(прежний) − H|: тон фона/заглушки (последняя строка FOGZ уровня) против прежнего
  G4 скачок:   Σ px·|ср.P − ср.T| + шум G2 < Σ px·|ср.Q − ср.T|: меньше перепад, когда вместо заглушки приходит текстура
H — среднее кадра «без города, взгляд по горизонту» в полосе 0..6° над строкой 136 (FOVY 62° из viewer/main.c), без радара.
Справочно (не гейт): край дальности — доля кадра дальше 225 м и |ср.A − H| там.
gate.py DIR [--json OUT]"""
import sys, glob, json, os, re, math, numpy as np
from PIL import Image
FOVY = 62.0; ROW0 = 136; BAND = int(round(math.tan(math.radians(6)) / math.tan(math.radians(FOVY / 2)) * ROW0))
def L(p): return np.asarray(Image.open(p).convert('RGB')).astype(float)
def key(M): return (M[..., 0] > 200) & (M[..., 1] < 70) & (M[..., 2] > 200)
def nrm(v): return float(np.linalg.norm(np.asarray(v, float)))
d = sys.argv[1]; res = {}; fz = {}
for ln in open(f'{d}/smoke.txt', errors='replace'):
    m = re.match(r'FOGZ level(\d) old(\d) rgb=([0-9a-f]{6})', ln)
    if m: v = int(m.group(3), 16); c = [v & 255, v >> 8 & 255, v >> 16 & 255]; fz[(int(m.group(1)), int(m.group(2)))] = c; fz[(int(m.group(1)), 'last')] = c
G = {'G1': [0.0, 0.0], 'G2': [0.0, 0.0], 'G3': [0.0, 0.0], 'G4': [0.0, 0.0]}
for n in range(1, 8):
    a = {'m': 0, 'AT': 0.0, 'FT': 0.0, 'UT': 0.0, 'RP': 0.0, 'R': np.zeros(3), 'P': np.zeros(3), 'Q': np.zeros(3), 'T': np.zeros(3), 'H': [], 'e': 0, 'eA': np.zeros(3), 'fr': 0}
    for f in sorted(glob.glob(f'{d}/L{n}h*_A.png')):
        b = f[:-6]
        if not all(os.path.exists(f'{b}_{k}.png') for k in 'FMETUHPQR'): continue
        A, F, T, P, Q, Hf, U, R = (L(f'{b}_{k}.png') for k in 'AFTPQHUR')
        M, E = key(L(b + '_M.png')), key(L(b + '_E.png'))
        for X in (M, E): X[190:, 370:] = False   # радар
        a['H'].append(Hf[ROW0 - BAND:ROW0, :370].reshape(-1, 3).mean(0)); a['fr'] += 1
        k = int(M.sum()); a['m'] += k
        if k:
            a['AT'] += np.linalg.norm(A[M] - T[M], axis=1).sum(); a['FT'] += np.linalg.norm(F[M] - T[M], axis=1).sum(); a['UT'] += np.linalg.norm(U[M] - T[M], axis=1).sum()
            # Measure repeat noise before averaging: opposite pixel changes must not cancel.
            a['RP'] += np.linalg.norm(R[M] - P[M], axis=1).sum()
            for c, X in (('P', P), ('Q', Q), ('T', T), ('R', R)): a[c] += X[M].sum(0)
        a['e'] += int(E.sum()); a['eA'] += A[E].sum(0)
    if a['fr'] != 4 or not a['m'] or (n, 'last') not in fz or (n, 1) not in fz:
        raise SystemExit(f'L{n}: incomplete evidence frames={a["fr"]}/4 mask={a["m"]}; FOGZ required')
    H = np.mean(a['H'], 0); r = {'H': H.round().tolist(), 'px': a['m']}
    if (n, 'last') in fz and (n, 1) in fz:
        r['tone_new'] = round(nrm(np.array(fz[(n, 'last')]) - H), 1); r['tone_old'] = round(nrm(np.array(fz[(n, 1)]) - H), 1)
        G['G3'][0] += r['tone_new']; G['G3'][1] += r['tone_old']
    if a['m']:
        k = a['m']; P, Q, T, R = a['P'] / k, a['Q'] / k, a['T'] / k, a['R'] / k
        nP = float(a['RP']) / k; r['noise_fog'] = round(float(a['UT']) / k, 1); r['noise_ph'] = round(nP, 1)
        r.update(fog_new=round(float(a['AT']) / k, 1), fog_old=round(float(a['FT']) / k, 1), ph_new=round(nrm(P - H), 1), ph_old=round(nrm(Q - H), 1),
                 pop_new=round(nrm(P - T), 1), pop_old=round(nrm(Q - T), 1))
        G['G1'][0] += a['AT'] + a['UT']; G['G1'][1] += a['FT']
        G['G2'][0] += k * (nrm(P - H) + nP); G['G2'][1] += k * nrm(Q - H); G['G4'][0] += k * (nrm(P - T) + nP); G['G4'][1] += k * nrm(Q - T)
    r['edge_share%'] = round(100 * a['e'] / (a['fr'] * 480 * 272), 3)
    if a['e']: r['edge_vs_H'] = round(nrm(a['eA'] / a['e'] - H), 1)
    res[f'L{n}'] = r; print(f'L{n}', r)
ok = True
for g, (new, old) in G.items():
    p = bool(new < old); ok &= p
    print(f"{g}: новое(+шум) {new:.1f} {'<' if p else '>='} прежнее {old:.1f}  {'PASS' if p else 'FAIL'}")
print('ИТОГ', 'PASS' if ok else 'FAIL')
if len(sys.argv) > 3 and sys.argv[2] == '--json': json.dump({'levels': res, 'gates': {k: [float(x) for x in v] for k, v in G.items()}, 'pass': bool(ok)}, open(sys.argv[3], 'w'), indent=1)
sys.exit(0 if ok else 1)

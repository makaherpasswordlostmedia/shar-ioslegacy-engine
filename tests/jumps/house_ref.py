#!/usr/bin/env python3
# Правки Роба 247/353 (09.10): эталон перепрыга дома J10 с jumpzone17 из записей PS2 (свой PCSX2 наблюдателя, трассы по 2 кадра PAL =
# 25 Гц): ps2_v103_house80_gas, ps2_v103_house90_gas, ps2_v103_house100_coast (общий снимок house-stage.p2s, рецепты
# tools/twins/recipes/ps2_v103_house*_repeat.json в ~/Downloads/shar-psp-ps2-w). Пишет tests/jumps/house_ps2.tsv для tests/jumps/house.c.
#   python3 tests/jumps/house_ref.py [КАТАЛОГ_o4] > tests/jumps/house_ps2.tsv
# Оси PS2 -> оси движка: z = −z. Кромка зоны (121,37; 8,71; 213,02), вдоль +z. Тангаж — asin(строка «вперёд» матрицы, y), нос вверх +.
# Правила (те же в house.c для порта): кромка — первый отсчёт с along ≥ 0; посадка за домом — первый удар (vy подскочила больше
# 2 м/с при падении быстрее 1 м/с) за коньком (along > 14,5) ниже верха стены дома (y < 7); нет посадки и машина не ушла дальше 14 м —
# «встала» у ската: место и тангаж через 3 с после кромки. Нос в полёте — наименьший тангаж от кромки до посадки и тангаж перед ней;
# скорость за коньком — горизонтальная скорость в первом отсчёте с along ≥ 20 (сколько машина потеряла на крыше).
import math, os, sys
O4 = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Downloads/shar-psp-ps2-w/build/twins/o4')
LX, LY, LZ = 121.37, 8.71, 213.02
RUNS = [  # id, запись, цель бота м/с (газ, пока ниже), кадр отпускания газа (накат) или None
    ('h80', 'ps2_v103_house80_gas', 80 / 3.6, None),
    ('h90', 'ps2_v103_house90_gas', 90 / 3.6, None),
    # Observer recipe releases cross once at frame 146 and never reapplies it.
    # Match that position along the route; a speed regulator would press gas
    # again after the ridge collision and would not reproduce this coast run.
    ('h100c', 'ps2_v103_house100_coast', 100 / 3.6, 146),
]
def load(p):
    with open(p) as f: lines = [l for l in f if not l.startswith('0 trace')]
    hdr = lines[0].rstrip('\n').split('\t'); rows = []
    for l in lines[1:]:
        v = l.rstrip('\n').split('\t')
        if len(v) == len(hdr): rows.append({k: float(x) for k, x in zip(hdr, v)})
    return rows
print('# правки 247/353: перепрыг дома J10 (jumpzone17), эталон PS2 — tests/jumps/house_ref.py; оси движка, м, м/с, градусы')
print('# id\tx0\ty0\tz0\th0\tv0\tцель м/с\tнакат с along (99 — нет)\tкромка м/с\tисход (over/stuck)\tпосадка along\tмин. тангаж\t'
      'тангаж перед посадкой\tвстала along\tтангаж стоя\tзапись\tскорость за коньком м/с')
for rid, run, vt, coast in RUNS:
    R = load(os.path.join(O4, run, 'trace.tsv'))
    S = []
    for r in R:
        z = -r['mat[14]']; vx, vz = r['car_vel[0]'], -r['car_vel[2]']
        S.append(dict(f=r['frame'] - R[0]['frame'], x=r['mat[12]'], y=r['mat[13]'], z=z, a=z - LZ, vh=math.hypot(vx, vz), vy=r['car_vel[1]'],
                      h=math.atan2(vx, vz), p=math.degrees(math.asin(max(-1., min(1., r['mat[9]']))))))
    s0 = next(s for s in S if s['a'] >= -29.6)                     # точка синхронизации — та же, что у строк jz17 в ramps_ps2.tsv
    coastA = next(s['a'] for s in S if s['f'] >= coast) if coast is not None else 99.
    k0 = next(i for i, s in enumerate(S) if s['a'] >= 0.)
    land = None
    for k in range(k0 + 1, len(S)):
        if S[k]['a'] > 14.5 and S[k]['y'] < 7. and S[k]['vy'] - S[k - 1]['vy'] > 2. and S[k - 1]['vy'] < -1.: land = k; break
    t3 = next((i for i in range(k0, len(S)) if S[i]['f'] - S[k0]['f'] >= 150), len(S) - 1)   # 3 с = 150 кадров PAL
    if land is not None:
        mp = min(s['p'] for s in S[k0:land]); out = 'over'; v20 = next(s['vh'] for s in S if s['a'] >= 20.)
        print('%s\t%.3f\t%.3f\t%.3f\t%.4f\t%.3f\t%.3f\t%.2f\t%.3f\t%s\t%.2f\t%.1f\t%.1f\tnan\tnan\t%s\t%.2f' % (
            rid, s0['x'], s0['y'], s0['z'], s0['h'], s0['vh'], vt, coastA, S[k0]['vh'], out, S[land]['a'], mp, S[land - 1]['p'], run, v20))
    else:
        assert max(s['a'] for s in S[k0:t3 + 1]) < 14.
        print('%s\t%.3f\t%.3f\t%.3f\t%.4f\t%.3f\t%.3f\t%.2f\t%.3f\t%s\tnan\tnan\tnan\t%.2f\t%.1f\t%s' % (
            rid, s0['x'], s0['y'], s0['z'], s0['h'], s0['vh'], vt, coastA, S[k0]['vh'], 'stuck', S[t3]['a'], S[t3]['p'], run + '\tnan'))

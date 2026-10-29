#!/usr/bin/env python3
"""Оценка кадра PSP на каждой секунде прогона бота (калиброванная модель, tools/bots/psp_calib.json: сверка с турами на железе 9D, 11A, 11B, средняя ошибка 4,3 %).
кадр, мс = база уровня + 0,324 x тыс. треугольников города в точке + 2,32 x ИИ-машины + 0,332 x машины трафика + 3,25 при разрушении; поправка по уровню (L1 .75, L3 .7, L7 .9) из сверки ночи.
Варианты кода: now (как в сборке 0516), hybrid (гибрид листов клеток), new (гибрид + дальность по перегрузке c25aa45e: спуск 20 м/с до 3,5x, подъём 6 м/с, пол 150 м).
  python3 frame_model.py TRACE.tsv LEVEL.shr [variant]   — построчная оценка в stdout"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; BOTS = HERE.parents[1] / 'bots'
CALIB = json.load(open(BOTS / 'psp_calib.json'))['coef']
BASE = {1: CALIB['base_L1'], 2: CALIB['base_L2'], 3: CALIB['base_L3'], 4: 14.88, 5: CALIB['base_L5'], 6: 14.88, 7: CALIB['base_L7']}   # L4, L6 — как в ночной модели (в калибровке туров их нет)
CORR = {1: .75, 3: .7, 7: .9}
K_KT, K_AI, K_TRF, K_BOOM = CALIB['per_ktris'], CALIB['per_ai_car'], CALIB['per_traffic_car'], CALIB['boom']
DD = np.array([250, 200, 180, 150, 115.]); HYB = np.array([24.5, 21.6, 20.2, 17.8, 14.6]) / 33.8; NOW = np.array([33.8, 29.3, 27.2, 23.8, 19.4]) / 33.8
BUDGET, FLOOR = 31.2, 150.
def scale(dd, curve): return float(np.interp(dd, DD[::-1], curve[::-1]))
def city_table(level_shr, cache_dir):
    """Карта «тыс. треуг. города по клеткам PVS» (tools/bots/city_tris.py), кэш по размеру и времени файла."""
    p = Path(level_shr); st = p.stat(); f = Path(cache_dir) / f'city_{p.parent.name}_{st.st_size}_{int(st.st_mtime)}.tsv'; f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists(): subprocess.check_call([sys.executable, str(BOTS / 'city_tris.py'), str(p), str(f)], stdout=subprocess.DEVNULL)
    a = np.array([[float(v) for v in l.split()] for l in open(f) if not l.startswith('#') and l.strip()])
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]   # x, z, среднее, худшее (тыс. треуг.)
def read_trace(path):
    names = None; rows = []
    for l in open(path):
        if l.startswith('#'): names = l[1:].split(); continue
        if l.strip(): rows.append([float(v) for v in l.split('\t')])
    names = names or ['t', 'x', 'y', 'z', 'foot', 'speed', 'ai_on', 'ai_chase', 'ai_race', 'ai_min_m', 'ai_mean_m', 'tr_cars', 'tr_peds', 'tr_parked', 'npc', 'replans', 'resets', 'destroyed3s', 'heat', 'status', 'stage', 'wallV', 'damage']
    a = np.array(rows); return {n: a[:, i] for i, n in enumerate(names) if i < a.shape[1]}
def series(tr, level, tbl, variant='new'):
    """Построчно: cpu мс, дальность, ктреуг (после варианта), доли статей. tr — словарь колонок trace.tsv."""
    X, Z, KM, KW = tbl; x, z = tr['x'], tr['z']; n = len(x)
    idx = np.array([int(np.argmin((X - xx) ** 2 + (Z - zz) ** 2)) for xx, zz in zip(x, z)])
    kt0 = KM[idx] * CORR.get(level, 1.0); kw0 = KW[idx] * CORR.get(level, 1.0)
    ai = tr.get('ai_on', np.zeros(n)); trc = tr.get('tr_cars', np.zeros(n)); de = (tr.get('destroyed3s', np.zeros(n)) > 0).astype(float)
    other = BASE[level] + K_AI * ai + K_TRF * trc + K_BOOM * de
    cpu = np.zeros(n); dd = np.full(n, 250.); kt = np.zeros(n); d = 250.; avg = None
    for t in range(n):
        if variant == 'now': s = scale(250, NOW)
        else: s = scale(d if variant == 'new' else 250., HYB)
        cur = other[t] + K_KT * kt0[t] * s; cpu[t] = cur; dd[t] = d if variant == 'new' else 250.; kt[t] = kt0[t] * s
        if variant == 'new':
            avg = cur if avg is None else avg + (cur - avg) * .5   # шаг трассы 1 с: сглаживание средней как у кадров (.08 на кадр) за секунду
            if avg > BUDGET + .3: d = max(FLOOR, d - 20. * min(3.5, 1 + max(0., avg - BUDGET) / 6))
            elif avg < BUDGET - 2.5: d = min(250., d + 6.)
    return dict(cpu=cpu, dd=dd, kt=kt, kw=kw0, ai=ai, trc=trc, de=de, base=np.full(n, BASE[level]), other=other)
if __name__ == '__main__':
    tr = read_trace(sys.argv[1]); lv = int(Path(sys.argv[2]).parent.name[1:]) if Path(sys.argv[2]).parent.name.startswith('l') else 1
    tbl = city_table(sys.argv[2], '/tmp/ae_city'); s = series(tr, lv, tbl, sys.argv[3] if len(sys.argv) > 3 else 'new')
    for t in range(len(s['cpu'])): print('%d\t%.1f\t%.1f\t%.0f\t%.1f' % (tr['t'][t], tr['x'][t], tr['z'][t], s['dd'][t], s['cpu'][t]))

#!/usr/bin/env python3
"""Самопроверка полосы Трассы на реальных данных пакета: python3 selftest.py [ПАКЕТ]  (по умолчанию последний build/final-*)."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tracks as T, frame_model as FM, numpy as np
pkg = sys.argv[1] if len(sys.argv) > 1 else T.latest_pkg(); bad = []
def check(name, ok, info=''):
    print(('ok   ' if ok else 'FAIL ') + name + (' ' + str(info) if info else '')); 
    if not ok: bad.append(name)
lp = T.level_path(pkg, 1); S = T.shooter(lp); sp = S.spawn
r = S.shot(sp[0], sp[1], sp[2], sp[3], None, '', 'holes')
check('L1: рендер у спавна рисует город', r['drawn'] > 10000, r['drawn'])
check('L1: у спавна под горизонтом нет пурпура (дыр)', r['holes'] is not None and r['holes'] < 1.0, r['holes'])
check('L1: видимость по кускам считается', 0 < r['vis_pieces'] <= r['pieces'], (r['vis_pieces'], r['pieces']))
a = S.shot(sp[0], sp[1], sp[2], sp[3], None, '', 'normal'); b = S.shot(sp[0], sp[1], sp[2], sp[3], None, '', 'normal')
check('рендер детерминирован', a['drawn'] == b['drawn'] and a['sub_tris'] == b['sub_tris'])
g = S.ground(sp[0], sp[2], sp[1]); check('земля под спавном по карте высот', g is not None and abs(g - sp[1]) < 2.0, (g, sp[1]))
# модель кадра: калибровочные точки (psp_calib.json: L2 езда без ИИ даёт базу + ктреуг)
tbl = FM.city_table(T.level_path(pkg, 2), tempfile.mkdtemp(prefix='ae_city_'))
n = 30; tr = dict(t=np.arange(n, dtype=float), x=np.full(n, -300.), z=np.full(n, -300.), y=np.zeros(n), ai_on=np.zeros(n), tr_cars=np.zeros(n), destroyed3s=np.zeros(n))
s0 = FM.series(tr, 2, tbl, 'now'); tr2 = dict(tr, ai_on=np.full(n, 3.)); s1 = FM.series(tr2, 2, tbl, 'now')
check('три ИИ-машины добавляют 3 x 2,32 мс', abs((s1['cpu'] - s0['cpu']).mean() - 3 * FM.K_AI) < 1e-6, (s1['cpu'] - s0['cpu']).mean())
sh = FM.series(dict(tr, ai_on=np.full(n, 3.)), 2, tbl, 'hybrid'); sn = FM.series(tr2, 2, tbl, 'new')
check('гибрид не тяжелее прежнего, дальность по перегрузке не тяжелее гибрида', sh['cpu'].mean() <= s1['cpu'].mean() + 1e-9 and sn['cpu'].mean() <= sh['cpu'].mean() + 1e-9, (s1['cpu'].mean(), sh['cpu'].mean(), sn['cpu'].mean()))
check('дальность не ниже пола', sn['dd'].min() >= FM.FLOOR - 1e-9, sn['dd'].min())
print('FAIL' if bad else 'OK'); sys.exit(1 if bad else 0)

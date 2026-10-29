#!/usr/bin/env python3
"""Сверка прогона tests/movie/newgame_scenario.txt: ролик новой игры fmv1a (viewer/main.c menuStartGame).
  newgame_check.py RUN_DIR   -> первая строка итог, код 0 = OK
  · NEW GAME: газета загрузки кончилась (LOADSHOW), потом ролик fmv1a открыт и показан (MSNFMV name=fmv1a have=1 played=1,
    кадров показано >= 25 до START, ошибок нет), START его пропустил (skipped=1)
  · снимок в ролике = тот же кадр fmv1a.rmv, разжатый ffmpeg на Маке (отпечаток картинки 4:3, tools/intro_check.py thumb),
    чужой кадр (intro) обязан разойтись
  · после ролика — облёт улицы старта уровня (строка MSNCAM req найденной камеры после MSNFMV)"""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import intro_check as ic, movie_export as mx

run = Path(sys.argv[1]); log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
kv = lambda l: dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
bad, info = [], []
fm = [(i, kv(l)) for i, l in enumerate(log) if l.startswith('MSNFMV ') and 'name=fmv1a' in l]
ls = next((i for i, l in enumerate(log) if l.startswith('LOADSHOW ')), None)
cam = next((i for i, l in enumerate(log) if l.startswith('MSNCAM req') and 'found=1' in l), None)
if not fm: bad.append('ролика fmv1a не было (нет MSNFMV name=fmv1a)')
else:
    i, d = fm[0]
    info.append(f"fmv1a: have={d.get('have')} played={d.get('played')} показано {d.get('shown')} пропущено={d.get('skipped')} ошибка {d.get('err')}")
    if d.get('have') != '1' or d.get('played') != '1' or int(d.get('shown', 0)) < 25 or d.get('err', '1') != '0':
        bad.append('ролик не сыгран как надо: ' + ' '.join(f'{k}={v}' for k, v in d.items()))
    if d.get('skipped') != '1': bad.append('START не пропустил ролик')
    if ls is None or ls > i: bad.append('ролик не после газеты загрузки (LOADSHOW)')
    if cam is None or cam < i: bad.append('после ролика нет облёта улицы (MSNCAM req … found=1)')
sh = [kv(l) for l in log if l.startswith('MSNFMVSHOT ') and 'clip=fmv1a' in l]
if not sh or not (run / 'fmv1a.png').exists(): bad.append('нет снимка ролика')
else:
    f = int(sh[0]['frame']); got = ic.window_frame(run / 'fmv1a.png')
    d0 = float(np.abs(ic.thumb(got) - ic.thumb(mx.reference_frame('fmv1a', f))).mean())
    dn = float(np.abs(ic.thumb(got) - ic.thumb(mx.reference_frame('intro', 300))).mean())
    info.append(f'снимок кадра {f}: разница с ffmpeg {d0:.2f} (<= {ic.TOL}); чужой кадр {dn:.2f} (> {ic.TOL})')
    if d0 > ic.TOL: bad.append(f'снимок не кадр fmv1a ({d0:.2f})')
    if dn <= ic.TOL: bad.append('сверка слепая: чужой кадр не различим')
if not any(l.startswith('END') for l in log): bad.append('нет END')
print('newgame fmv1a: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(bad)))
for x in info: print('  ' + x)
sys.exit(1 if bad else 0)

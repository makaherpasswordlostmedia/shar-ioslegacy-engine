#!/usr/bin/env python3
"""Гейт экранов вокруг игры (tools/screens_gate.sh): smoke.txt и снимки прогона по tools/screens_scenario.txt.
  python tools/screens_check.py RUN_DIR --data DIR [--copy DIR] [--expect-fail K1,K2] [--news-red]
  RUN_DIR = build/smoke/<время>, DIR = где EBOOT и данные
  (1) пакеты boot.shr и load.shr в DIR = свежей выгрузке tools/load_export.py с диска (иначе макеты не про то, что рисовал движок)
  (1б) [news_size] газета экрана загрузки почти на весь экран (правка Роба 35): высота места газеты >= NEWS_MIN_H высоты
      экрана, в кадре целиком; --news-red — выгрузка прежней раскладки (NEWS_NATIVE = False, отрицательный контроль)
  (2) пять снимков SCRSHOT есть: license, bootload, splash (титульный ПРОСТОЯ), loading (газета уже на месте, часы >=
      LOAD_SPIN_S), loadingfe — кадр окна против макета того же экрана при том же состоянии (доля загрузки, часы кадров,
      теги), отпечаток 60x34 (блоки 8x8), средняя разница ≤ TOL из 255; отрицательный контроль — соседний экран
      (лицензия/BootupLoad, Press START/LOADING титульного, Loading/LoadingFE): в области, где их макеты различаются
      (блоки 4x4), снимок похож на свой (≤ TOL) и не похож на соседний (> TOL)
  (2б) загрузка уровня и меню сняты на часах экрана ≥ 0,5 с (сценарий держит снимок): в области, где кадры огня, анимации
      и точек LOADING сменились, снимок = макету на этих часах и ≠ макету на нулевых — смена кадров по часам работает
      хотя бы на одном экране
  (3) порядок (правка Роба 33): лицензия → BootupLoad → ролики (INTRO) → СРАЗУ меню (MENU; титульного на старте нет) →
      простой → титульный (TITLE on, снимок splash) → нажатие → меню → загрузка уровня → игра (GAME) → загрузка меню → меню;
      сценарий дошёл до END. [title_boot] титульный или прежний SPLASH до первого меню — провал
  (4) [title_press] титульный простоя ушёл с ПЕРВОГО нажатия (presses=1) и отклик ≤ TITLE_LAT_MS (правка Роба 24)
  (5) [load_min] показ загрузки уровня ≥ LOAD_MIN_S (LOADSHOW); [spin_smooth] газета влетает ровно: кадров разворота
      ≥ 80% от 60 в секунду, самый длинный промежуток ≤ SPIN_GAP_MS (LOADSPIN)
  --expect-fail K1,K2 — отрицательный прогон (подброшенные флаги titledeaf/loadfast/spinlag или прежний EBOOT): код 0,
      только если провалы с КАЖДЫМ из ключей пойманы
--copy DIR: снимки 480x272 и макеты рядом -> DIR/scr_<имя>.png, DIR/scr_<имя>_mock.png
Код выхода 0 = PASS; первая строка вывода — итог."""
import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_export as LX  # noqa: E402

TOL = 8.0
SHOTS = ['license', 'bootload', 'splash', 'loading', 'loadingfe']
PACK_SCR = {'boot': LX.PACKS['boot'], 'load': LX.PACKS['load']}
ANIMATED = {'loading': 0.5, 'loadingfe': 0.5}   # снимок держится до часов экрана ≥ N с: кадры огня/анимации не нулевые
NEG = {'license': 'bootload', 'bootload': 'license', 'splash': 'splash_loading',
       'loading': 'loadingfe', 'loadingfe': 'loading'}     # контроль: соседний экран — самый похожий
NEG_STATE = {'splash_loading': ('boot', 'splash', dict(PROGRESS=0, T=0.0, LEVEL=0, show={'ALWAYS', 'LOADING'}))}   # контроль без снимка
TITLE_LAT_MS = 300      # правка Роба 24: титульный уходит с первого нажатия не позже
LOAD_SPIN_S, LOAD_MIN_S = 0.9, 2.0   # viewer/main_frontend.h: разворот газеты и минимальный показ загрузки уровня (15.10: 3,5 → 2,0 по замеру PS2; LOAD_MIN_OLD=1 — 3,5)
SPIN_GAP_MS = 40.0


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def window_frame(p):   # снимок окна PPSSPP: заголовок сверху, кадр 480x272 снизу
    im = Image.open(p).convert('RGB'); w, h = im.size; ch = min(h, round(w * 272 / 480))
    return im.crop((0, h - ch, w, h)).resize((480, 272), Image.LANCZOS)


def thumb(im, size=(60, 34)):
    return np.asarray(im.convert('RGB').resize(size, Image.BOX), np.float32)


def region_diffs(got, own, neg):
    """Контроль в области, где макеты своего и соседнего экрана различаются (блоки 4x4, разница > 16):
    -> (разница снимка со своим макетом там, с соседним там, доля области)"""
    g, o, n = (thumb(x, (120, 68)) for x in (got, own, neg))
    m = np.abs(o - n).mean(-1) > 16
    if not m.any():
        return None, None, 0.0
    return float(np.abs(g - o)[m].mean()), float(np.abs(g - n)[m].mean()), float(m.mean())


def state_of(d):
    show = {'ALWAYS'} | ({d['show']} if d.get('show', '-') not in ('-', '') else set())
    return dict(PROGRESS=int(d['prog']), T=float(d['t']), LEVEL=int(d['level']), show=show)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--data', required=True); ap.add_argument('--copy')
    ap.add_argument('--expect-fail', default=''); ap.add_argument('--news-red', action='store_true')
    a = ap.parse_args()
    keyed = set()
    run, data = Path(a.run), Path(a.data)
    lines = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    bad, info = [], []
    # (1) пакеты = свежая выгрузка с диска
    res = {}
    with tempfile.TemporaryDirectory() as td:
        for pk in PACK_SCR:
            fresh = Path(td) / ('%s.shr' % pk)
            res[pk] = LX.export(pk, fresh, mocks=False)
            got = data / ('%s.shr' % pk)
            if a.news_red and pk == 'load':                  # отрицательный контроль (1б): прежняя раскладка газеты
                LX.NEWS_NATIVE = False; res[pk] = LX.export(pk, Path(td) / 'load_old.shr', mocks=False); LX.NEWS_NATIVE = True
            if not got.exists() or got.read_bytes() != fresh.read_bytes():
                bad.append('%s в %s не совпадает со свежей выгрузкой load_export.py (%s)' % (got.name, data,
                           'нет файла' if not got.exists() else '%d Б против %d Б' % (got.stat().st_size, fresh.stat().st_size)))
    # (1б) газета почти на весь экран
    news = next((t for t in res['load']['screens']['loading'] if t['type'] == LX.U.T_IMG and t.get('field') == 'LEVEL'), None)
    if news is None:
        bad.append('[news_size] на экране загрузки нет газеты'); keyed.add('news_size')
    else:
        x, y, w, h = news['dst']
        info.append('газета: место %dx%d в (%d, %d) — %.0f%% высоты экрана (нужно ≥ %.0f%%)' % (w, h, x, y, 100 * h / LX.U.DST_H, 100 * LX.NEWS_MIN_H))
        if h < LX.NEWS_MIN_H * LX.U.DST_H:
            bad.append('[news_size] газета %dx%d — %.0f%% высоты экрана (< %.0f%%)' % (w, h, 100 * h / LX.U.DST_H, 100 * LX.NEWS_MIN_H)); keyed.add('news_size')
        if y < 0 or y + h > LX.U.DST_H or x < 0 or x + w > LX.U.DST_W:
            bad.append('[news_size] газета за краем экрана'); keyed.add('news_size')
    # (2) снимки против макетов
    shots = {kv(l)['name']: kv(l) for l in lines if l.startswith('SCRSHOT ')}
    mocks = {}
    # правка Роба 89 (30.09): на экранах пакета boot.shr поверх — рамка меню (экран tvmovie, viewer/main.c scrFrame)
    tv = LX.mock(res['boot'], 'tvmovie', {}, bg=(0, 0, 0, 0)) if 'boot' in res else None
    def framed(pk, im):
        if pk != 'boot' or tv is None: return im
        base = im.convert('RGBA'); base.alpha_composite(tv.convert('RGBA')); return base.convert(im.mode)
    for nm, (pk, sc, stt) in NEG_STATE.items():
        mocks[nm] = framed(pk, LX.mock(res[pk], sc, stt))
    for name in SHOTS:
        d = shots.get(name)
        if not d:
            bad.append('нет снимка %s (строки SCRSHOT)' % name); continue
        pk = d['pack']; sc = PACK_SCR[pk][int(d['scr'])]
        mocks[name] = framed(pk, LX.mock(res[pk], sc, state_of(d)))
    animated_ok = []
    for name, d in ((n, shots[n]) for n in SHOTS if n in shots):
        p = run / ('%s.png' % name)
        if not p.exists():
            bad.append('нет файла снимка %s' % p.name); continue
        got = window_frame(p)
        d0 = float(np.abs(thumb(got) - thumb(mocks[name])).mean())
        neg = NEG[name]
        ro, rn, frac = region_diffs(got, mocks[name], mocks[neg]) if neg in mocks else (None, None, 0.0)
        info.append('%-15s %s/%s прогресс %s часы %s: разница %.2f (≤ %.0f); в области отличий от %s (%.1f%% кадра): '
                    'свой %s, чужой %s (> %.0f)' % (name, d['pack'], PACK_SCR[d['pack']][int(d['scr'])], d['prog'], d['t'], d0,
                                                     TOL, neg, frac * 100, '%.2f' % ro if ro is not None else '—',
                                                     '%.2f' % rn if rn is not None else '—', TOL))
        if d0 > TOL:
            bad.append('%s: снимок != макету (%.2f > %.0f)' % (name, d0, TOL))
        if ro is None or ro > TOL:
            bad.append('%s: в области отличий от %s снимок не похож на свой макет (%s)' % (name, neg, ro))
        if rn is not None and rn <= TOL:
            bad.append('%s: контроль %s не различим (%.2f ≤ %.0f) — сверка слепая' % (name, neg, rn, TOL))
        if name == 'loading' and float(d['t']) < LOAD_SPIN_S:
            bad.append('loading: снимок на часах %.2f с — газета ещё в полёте (< %.1f с), макет её не рисует' % (float(d['t']), LOAD_SPIN_S))
        if name in ANIMATED:                              # кадры огня / анимации / точек по часам экрана (F_RATE, viewer/ui.c)
            pk = d['pack']; sc = PACK_SCR[pk][int(d['scr'])]; st0 = dict(state_of(d), T=0.0)
            ro0, rn0, fr0 = region_diffs(got, mocks[name], LX.mock(res[pk], sc, st0))
            info.append('%-15s часы %.2f с против нулевых: область смены кадров %.1f%% кадра, свой %s, на нулевых часах %s' % (
                '', float(d['t']), fr0 * 100, '%.2f' % ro0 if ro0 is not None else '—', '%.2f' % rn0 if rn0 is not None else '—'))
            if float(d['t']) < ANIMATED[name]:
                bad.append('%s: снимок на часах %.2f с < %.1f — кадры не проверены (flag loadshot/feshot N)' % (name, float(d['t']), ANIMATED[name]))
            elif ro0 is None:       # кадры на этом размере почти одинаковы (огонь 26x28: разница ≤ 28 из 255) — не различить
                info.append('%-15s кадры на часах %.2f с неотличимы от нулевых на этом размере — проверка по часам на других экранах' % ('', float(d['t'])))
            elif ro0 > TOL or rn0 <= TOL:
                bad.append('%s: кадры по часам не совпали (свой %.2f, нулевые часы %.2f)' % (name, ro0, rn0))
            else:
                animated_ok.append(name)
        if a.copy:
            c = Path(a.copy); c.mkdir(parents=True, exist_ok=True)
            got.save(c / ('scr_%s.png' % name)); mocks[name].convert('RGB').save(c / ('scr_%s_mock.png' % name))
    if not animated_ok:
        bad.append('смена кадров по часам не подтверждена ни на одном экране (%s)' % ', '.join(ANIMATED))
    # (3) порядок экранов в журнале
    seq = []
    for l in lines:
        t = l.split()[0] if l.split() else ''
        if t == 'SCRSHOT':
            seq.append(kv(l)['name'])
        elif t in ('INTRO', 'MENU', 'GAME', 'SPLASH'):
            seq.append(t)
        elif t == 'TITLE' and len(l.split()) > 1:
            seq.append('TITLE_' + l.split()[1].upper())
    want = ['license', 'bootload', 'INTRO', 'MENU', 'TITLE_ON', 'splash', 'TITLE_OFF', 'loading', 'GAME', 'MENU', 'loadingfe']
    it = iter(seq)
    miss = [w for w in want if not any(w == s for s in it)]
    info.append('порядок: ' + ' → '.join(x for i, x in enumerate(seq) if i == 0 or seq[i - 1] != x))
    if miss:
        bad.append('порядок экранов не тот, не нашлось по порядку: ' + ', '.join(miss))
    first_menu = seq.index('MENU') if 'MENU' in seq else len(seq)
    early = [x for x in seq[:first_menu] if x in ('splash', 'SPLASH', 'TITLE_ON', 'splash_loading')]
    if early or 'SPLASH' in seq:
        bad.append('[title_boot] титульный показан на старте, до меню (%s) — правка Роба 33: сразу меню' % ', '.join(early or ['SPLASH']))
        keyed.add('title_boot')
    # (4) титульный простоя уходит с первого нажатия
    offs = [kv(l) for l in lines if l.startswith('TITLE off')]
    if not offs:
        bad.append('[title_press] титульный простоя не ушёл по нажатию (нет TITLE off)'); keyed.add('title_press')
    for d in offs:
        info.append('титульный: показан %s с, нажатий %s, отклик %s мс (≤ %d)' % (d['shown'], d['presses'], d['lat_ms'], TITLE_LAT_MS))
        if int(d['presses']) != 1 or not 0 <= float(d['lat_ms']) <= TITLE_LAT_MS:
            bad.append('[title_press] титульный ушёл не с первого нажатия / поздно (нажатий %s, отклик %s мс)' % (d['presses'], d['lat_ms']))
            keyed.add('title_press')
    # (5) показ загрузки уровня и разворот газеты
    shows = [kv(l) for l in lines if l.startswith('LOADSHOW ')]; spins = [kv(l) for l in lines if l.startswith('LOADSPIN ')]
    if not shows:
        bad.append('[load_min] нет строки LOADSHOW'); keyed.add('load_min')
    for d in shows:
        info.append('загрузка уровня показана %s мс (≥ %.0f)' % (d['ms'], LOAD_MIN_S * 1000))
        if float(d['ms']) < LOAD_MIN_S * 1000 - 20:
            bad.append('[load_min] загрузка показана %s мс < %.0f' % (d['ms'], LOAD_MIN_S * 1000)); keyed.add('load_min')
    if not spins:
        bad.append('[spin_smooth] нет строки LOADSPIN'); keyed.add('spin_smooth')
    for d in spins:
        fr, gap, sec = int(d['frames']), float(d['gap_ms']), float(d['s'])
        info.append('газета влетает: %d кадров за %.2f с, самый длинный промежуток %.1f мс (≤ %.0f)' % (fr, sec, gap, SPIN_GAP_MS))
        if fr < 0.8 * 60 * LOAD_SPIN_S or gap > SPIN_GAP_MS:
            bad.append('[spin_smooth] разворот газеты рывками (%d кадров, промежуток %.1f мс)' % (fr, gap)); keyed.add('spin_smooth')
    if not any(l.startswith('END') for l in lines):
        bad.append('нет END: упал / завис')
    if a.expect_fail:                                     # отрицательный прогон: каждый подброшенный провал пойман
        want_k = [k for k in a.expect_fail.split(',') if k]; miss_k = [k for k in want_k if k not in keyed]
        print(('screens: КРАСНЫЙ как надо — пойманы %s' % ', '.join(want_k)) if not miss_k else
              'screens: НЕ КРАСНЫЙ — не пойманы %s' % ', '.join(miss_k))
        for b in bad:
            print('  - ' + b)
        return 0 if not miss_k else 1
    print(('screens: FAIL — ' + '; '.join(bad)) if bad else 'screens: PASS')
    for i in info:
        print('  ' + i)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

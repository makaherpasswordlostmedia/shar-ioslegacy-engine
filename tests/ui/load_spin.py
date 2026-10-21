#!/usr/bin/env python3
"""Гейт правки Роба 336 (05.10: «на экране загрузки лучи были анимированы, крутились по-живому в разные стороны»): звёзды
экрана загрузки уровня (Loading.scr, слои Overlay1/Overlay0) крутятся вокруг центра экрана, как у оригинала — 18 °/с,
Overlay0 по часовой, Overlay1 против (tools/load_export.py STAR_*, viewer/ui.c drawSpin).
   python3 tests/ui/load_spin.py        -> код 0 = зелёный
Шесть прогонов безголового эмулятора (без окна, без звука) одного EBOOT (LOAD_SPIN_EBOOT, по умолчанию build/EBOOT.PBP):
главное меню -> NEW GAME -> газета, снимок экрана загрузки на часах экрана >= T1 и >= T2 («flag loadshot N»):
  зелёный — свежий load.shr (звёзды отдельными слоями);
  красный — load.shr с LOAD_STARS_OLD=1 (прежний сведённый неподвижный фон): обязан провалиться по (2) и (3);
  красный 2 — пакет, где слои крутятся наоборот (Overlay0 против часовой): обязан провалиться по (2б).
Проверки: (1) в пакете два слоя звезды: Overlay0 -18 °/с, Overlay1 +18 °/с (против часовой), центр (240, 136), квадрат 630;
(2) угол звёзд на каждом снимке (подгонка макетом load_export.mock по часам T' у часов снимка t из строки SCRSHOT, только
фон — газета, фитиль и надписи вырезаны) = 18 °/с x t в пределах ANG_TOL; подгонка не слепая — на нулевом угле разница
заметно больше; (2б) направление: макет со слоями наоборот (Overlay0 против часовой) дальше от снимка на DIR_MIN; (3) между снимками на разных часах фон меняется (звёзды не стоят); (4) снимок = макету на его часах
(отпечаток 60x34, ≤ TOL). Время чтения уровня (строка LOADREAD движка) печатается для обоих пакетов — для журнала.
Свой HOME эмулятора: LOAD_SPIN_HOME (по умолчанию build/twins/ppsspp_home_spin); корень данных — TWINS_ROOT."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins')); sys.path.insert(0, str(ROOT / 'tools'))
import common as C, port as P  # noqa: E402
import load_export as LX  # noqa: E402
T1, T2 = 3.5, 6.0            # часы снимков, с (снимок держится до них; раньше середины чтения клеток не бывает)
ANG_TOL = 1.0                # допуск угла, °
TOL = 8.0                    # отпечаток 60x34 против макета (как tools/screens_check.py)
MOVE_MIN = 1.0               # (3): средняя разница фона двух снимков, из 255
DIR_MIN = 0.5                # (2б): макет своего направления ближе к снимку, чем зеркальный, хотя бы на столько
SCEN = ['flag menu', 'wait 1', 'press start', 'wait 1', 'press start', 'wait 1', 'flag loadshot %.2f', 'press start', 'wait 1.5',
        'press cross', 'wait 9', 'end']


def export(old):
    td = Path(tempfile.mkdtemp(prefix='load_spin_'))
    env = dict(os.environ); env.pop('LOAD_STARS_OLD', None)
    if old: env['LOAD_STARS_OLD'] = '1'
    subprocess.run([sys.executable, str(ROOT / 'tools/load_export.py'), '--pack', 'load', '--out', str(td / 'load.shr')],
                   check=True, capture_output=True, env=env)
    return td / 'load.shr'


def run(name, pack, shot_at):
    lines = [l % shot_at if '%' in l else l for l in SCEN]
    d, man = P.stage_full(C.OUT / 'scen', name, '\n'.join(lines) + '\n', 5)
    (d / 'load.shr').unlink(); shutil.copy2(pack, d / 'load.shr')
    eb = Path(os.environ.get('LOAD_SPIN_EBOOT', str(ROOT / 'build/EBOOT.PBP')))
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eb, d / 'EBOOT.PBP')
    home = Path(os.environ.get('LOAD_SPIN_HOME', str(C.OUT / 'ppsspp_home_spin'))); home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN),
               SDL_AUDIODRIVER='dummy')
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', '--timeout=300', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, 360)
    for b in d.glob('*.bmp'): P.bmp_to_png(b, b.with_suffix('.png'))
    txt = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    shot = next((dict(p.split('=', 1) for p in l.split()[1:] if '=' in p) for l in txt.splitlines()
                 if l.startswith('SCRSHOT ') and 'name=loading' in l), None)
    rd = re.search(r'^LOADREAD ms=(\d+) frames=(\d+) skip=(\d+)', txt, re.M)
    img = np.asarray(Image.open(d / 'loading.png').convert('RGB'), np.float32) if (d / 'loading.png').exists() else None
    return dict(dir=d, shot=shot, img=img, read=rd.groups() if rd else None)


def bg_mask(dl):
    """фон: без газеты, фитиля, огня, динамита и надписей (их места + 4 px)"""
    m = np.ones((LX.U.DST_H, LX.U.DST_W), bool)
    for t in dl:
        if t['name'] in ('BGColour', 'LoadBackground') or t.get('spin') is not None:
            continue
        x, y, w, h = t['dst']
        m[max(0, y - 4):max(0, y + h + 4), max(0, x - 4):max(0, x + w + 4)] = False
    return m


def state(s, T):
    return dict(PROGRESS=int(s['prog']), T=T, LEVEL=int(s['level']), show={'ALWAYS'} | ({s['show']} if s.get('show', '-') not in ('-', '') else set()))


def fit(res, r, mask):
    """угол звёзд снимка: часы T' у t (±1 с, шаг 0,02 с = 0,36°) с наименьшей разницей фона -> (T', разница, на нулевом угле)"""
    t = float(r['shot']['t'])
    def diff(T):
        m = np.asarray(LX.mock(res, 'loading', state(r['shot'], T)).convert('RGB'), np.float32)
        return float(np.abs(m - r['img'])[mask].mean())
    cand = [(diff(T), T) for T in np.arange(t - 1.0, t + 1.0001, 0.02)]
    d, T = min(cand)
    return T, d, diff(0.0)


def mirror(res):
    """макет с обратным направлением слоёв (Overlay0 против часовой, Overlay1 по часовой) — контроль направления"""
    sc = dict(res['screens']); sc['loading'] = [dict(t, spin=-t['spin']) if t.get('spin') is not None else t for t in sc['loading']]
    return dict(res, screens=sc)


def thumb(a):
    return np.asarray(Image.fromarray(a.astype(np.uint8)).resize((60, 34), Image.BOX), np.float32)


def judge(tag, res, runs, mask):
    bad = []
    deg = LX.STAR_DEG_S
    for r in runs:
        if r['img'] is None or r['shot'] is None:
            bad.append('нет снимка экрана загрузки (%s)' % r['dir'].name); continue
        t = float(r['shot']['t']); T, d, d0 = fit(res, r, mask)
        mock = np.asarray(LX.mock(res, 'loading', state(r['shot'], t)).convert('RGB'), np.float32)
        full = float(np.abs(thumb(mock) - thumb(r['img'])).mean())
        mir = np.asarray(LX.mock(mirror(res), 'loading', state(r['shot'], T)).convert('RGB'), np.float32)
        dm = float(np.abs(mir - r['img'])[mask].mean())   # те же углы, слои наоборот: Overlay0 против часовой, Overlay1 по
        print('  %s: часы снимка %.3f с — угол звёзд ждём %.1f°, по подгонке %.1f° (разница фона %.2f, на нулевом угле %.2f, '
              'направление наоборот %.2f); снимок против макета %.2f; чтение %s' % (tag, t, deg * t, deg * T, d, d0, dm, full,
                                                          'мс=%s кадров=%s пропущено=%s' % r['read'] if r['read'] else '—'))
        if abs(T - t) * deg > ANG_TOL: bad.append('угол %.1f° вместо %.1f° (часы %.2f)' % (deg * T, deg * t, t))
        if d0 < d + 1.0: bad.append('подгонка слепая: на нулевом угле %.2f против %.2f' % (d0, d))
        if dm < d + DIR_MIN: bad.append('направление не то: с зеркальным макетом %.2f, со своим %.2f' % (dm, d))
        if full > TOL: bad.append('снимок не похож на макет (%.2f > %.0f)' % (full, TOL))
    if all(r['img'] is not None for r in runs) and len(runs) == 2:
        mv = float(np.abs(runs[0]['img'] - runs[1]['img'])[mask].mean())
        print('  %s: фон между снимками на %.2f и %.2f с меняется на %.2f (нужно > %.1f)' % (
            tag, float(runs[0]['shot']['t']) if runs[0]['shot'] else -1, float(runs[1]['shot']['t']) if runs[1]['shot'] else -1, mv, MOVE_MIN))
        if mv <= MOVE_MIN: bad.append('звёзды стоят: фон двух снимков почти одинаков (%.2f)' % mv)
    print('%s: %s' % (tag, 'зелёный' if not bad else 'КРАСНЫЙ — ' + '; '.join(bad)))
    return not bad


def main():
    new, old = export(False), export(True)
    LX.STARS_OLD = False
    res = LX.export('load', Path(tempfile.mkdtemp(prefix='load_spin_res_')) / 'load.shr', mocks=False)
    dl = res['screens']['loading']
    sp = sorted((t['name'], t['spin'], t['pivot'], t['dst'][2]) for t in dl if t.get('spin') is not None)
    ok1 = sp == [('Overlay0', -LX.STAR_DEG_S, (240.0, 136.0), 630), ('Overlay1', LX.STAR_DEG_S, (240.0, 136.0), 630)]
    print('(1) слои звезды в пакете: %s — %s' % (sp, 'ok' if ok1 else 'НЕ ТАК'))
    mask = bg_mask(dl)
    flip = Path(tempfile.mkdtemp(prefix='load_spin_flip_')) / 'load.shr'   # красный 2: слои крутятся наоборот (тот же пакет, знаки)
    keep = LX.Loader.stars
    LX.Loader.stars = lambda self, a: [dict(t, spin=-t['spin']) for t in keep(self, a)]
    try: LX.export('load', flip, mocks=False)
    finally: LX.Loader.stars = keep
    green = [run('load_spin_g%d' % i, new, T) for i, T in enumerate((T1, T2))]
    red = [run('load_spin_r%d' % i, old, T) for i, T in enumerate((T1, T2))]
    red2 = [run('load_spin_f%d' % i, flip, T) for i, T in enumerate((T1, T2))]
    ok = judge('зелёный (свежий пакет)', res, green, mask) and ok1
    caught = not judge('красный (LOAD_STARS_OLD=1, прежний неподвижный фон)', res, red, mask)
    caught2 = not judge('красный 2 (слои крутятся наоборот)', res, red2, mask)
    print('ИТОГ:', 'зелёный' if ok and caught and caught2 else 'КРАСНЫЙ (зелёный %s, красные пойманы %d/2)' % (
        'ok' if ok else 'FAIL', int(caught) + int(caught2)))
    return 0 if ok and caught and caught2 else 1


if __name__ == '__main__':
    sys.exit(main())

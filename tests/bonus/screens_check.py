#!/usr/bin/env python3
"""Разбор прогона родных экранов, облёта и музыки бонус-игры (tests/bonus/screens.sh, сценарий tests/bonus/screens_scenario.txt).
  python tests/bonus/screens_check.py RUN_DIR [--expect-fail]
Проверки (каждая — числом из smoke.txt и снимков игры):
  ui      пакет bonus/mini.shr открыт (BONUS ev=ui ok=1 screens=9); экраны mmchar, mmtrack, pause, summary показаны из пакета
          (ev=uiscreen pak=1); снимок каждого совпадает с кадром, собранным из того же пакета на Маке (tools/ui_export.py render)
          по непрозрачным пикселям экрана: средняя разница RGB <= UI_TOL и непрозрачных пикселей >= 1500
  flyby   облёт одновременно с отсчётом: ev=flyby frames=120, ev=flyby_end skip=0 и показано >= 60 кадров после ev=count в каждой гонке; позы
          кадров 0/30/60/90/119 (ev=flycam) — как в minigamecam.p3d диска (tools/bonus/flyby_export.py frames, допуск 1 см);
          снимок облёта не пустой и не вид сверху (разница > 15)
  music   у каждой гонки ev=music с дорожкой из альтернатив SuperSprint композиции (l1_music.rms), id >= 0; у разных трасс — разные
  race    вторая гонка дошла до итогов (ev=done) и выход в главное меню (ev=exit ok=1, MENU n=2+)
--expect-fail — код 0, только если провалились ui, flyby и music (красный: сборка -DBONUS_SCREENS_OLD=1)."""
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/bonus'))
UI_TOL = 10.0  # fixed acceptance bound; never widen via environment


def kv(l): return dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)


_RES = None


def pack_res():
    """тот же пакет, что у игры (tools/bonus/screens_export.py), — экраны и картинки после квантования"""
    global _RES
    if _RES is None:
        import screens_export as E
        tmp = ROOT / 'build/gates/bonus_screens/mini_check.shr'; tmp.parent.mkdir(parents=True, exist_ok=True)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            _RES = E.export(tmp, mocks=False)
        _RES['E'] = E
    return _RES


def overlay(parts):
    """parts: [(экран, состояние, выбранный пункт)] -> RGBA кадр пакета на прозрачном фоне"""
    r = pack_res(); U = r['E'].U
    img = Image.new('RGBA', (U.DST_W, U.DST_H), (0, 0, 0, 0))
    for sc, st, sel in parts:
        img = U.render(r['screens'][sc], U.DST_W, U.DST_H, st, r['qbitmaps'], img, None, sel)
    return img


def compare(shot, ov):
    a = np.asarray(Image.open(shot).convert('RGB'), np.float64)
    o = np.asarray(ov, np.float64)
    m = o[..., 3] >= 250
    n = int(m.sum())
    if not n:
        return 1e9, 0
    return float(np.abs(a[m] - o[..., :3][m]).mean()), n


def main():
    run = Path(sys.argv[1]); expect_fail = '--expect-fail' in sys.argv
    log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    ev = [(i, kv(l)) for i, l in enumerate(log) if l.startswith('BONUS ')]
    menus = [l for l in log if l.startswith('MENU ')]
    errs, lines = {}, []

    def need(name, ok, msg):
        lines.append(f"  {'ok  ' if ok else 'FAIL'} {name}: {msg}")
        if not ok:
            errs[name] = msg

    def evs(name): return [(i, e) for i, e in ev if e.get('ev') == name]
    # ---- ui
    ui = evs('ui'); shown = {e.get('name') for _, e in evs('uiscreen') if e.get('pak') == '1'}
    st_ = {e.get('scr'): e for _, e in evs('uistate')}
    diffs = {}
    import screens_export as E
    T = E.CUR_TAGS
    try:
        if 'mmchar' in st_:
            s = st_['mmchar']; chr_ = int(s['chr'])
            st = {'show': {'ALWAYS', T[chr_]}, 'ROW5': int(s['veh']), 'ROW6': int(s['rate']), 'ROW7': 0 if s['focus'] == '1' else 1}
            st['ROW%d' % chr_] = 1
            if s.get('ready') == '1': st['show'].add(E.LOCK_TAGS[chr_])
            diffs['mmchar'] = compare(run / 'bonus_mmchar.png', overlay([('mmchar', st, -1), ('mmhints', {'show': {'ALWAYS'}}, -1)]))
        if 'mmtrack' in st_:
            s = st_['mmtrack']; chr_ = int(s['chr'])
            st = {'show': {'ALWAYS', T[chr_]}, 'ROW5': int(s['veh']), 'ROW6': int(s['rate']), 'ROW7': 1}
            st['ROW%d' % chr_] = 1
            st2 = {'show': {'ALWAYS', T[int(s['track']) - 1], *E.TRACK_TAGS}, 'ROW9': int(s['laps']), 'ROW10': int(s['rev'])}
            r = pack_res(); mask = int(s['open'], 16)
            dl = []
            for item in r['screens']['mmtrack']:
                q = dict(item)
                if q['tag'] in E.TRACK_TAGS and not mask & (1 << E.TRACK_TAGS.index(q['tag'])):
                    q['color'] = [(v * 64 + 127) // 255 for v in q.get('color', [255]*4)[:3]] + [q.get('color', [255]*4)[3]]
                dl.append(q)
            r['screens']['mmtrack_live'] = dl
            diffs['mmtrack'] = compare(run / 'bonus_mmtrack.png', overlay([('mmchar', st, -1), ('mmtrack_live', st2, -1), ('mmhints', {'show': {'ALWAYS'}}, -1)]))
        if (run / 'bonus_pause.png').exists() and 'pause' in shown:
            diffs['pause'] = compare(run / 'bonus_pause.png', overlay([('minipause', {'show': {'ALWAYS'}}, 0)]))
        rows = sorted((e for _, e in evs('sumrow')), key=lambda e: int(e['k']))[:4]
        if (run / 'bonus_summary.png').exists() and len(rows) == 4:
            r = pack_res()
            parts = [('msbase', {'show': {'ALWAYS'}}, -1)]
            for e in rows:
                k = int(e['k']); sc = 'msrow%d' % k
                kings = e['king'].split(',')
                show = {'ALWAYS'} | ({E.KING_TOTAL} if kings[0] == '1' else set()) | ({E.KING_LAP} if kings[1] == '1' else set())
                txt = {'ROW2': e['wins'], 'ROW3': e['pts'], 'ROW4': e['total'], 'ROW5': e['best']}
                dl = [dict(t, strings=[txt[t['field']]], fmt='none', field='NONE') if t['type'] == E.U.T_TEXT and t['field'] in txt else t
                      for t in r['screens'][sc]]
                r['screens'][sc + '_live'] = dl
                parts.append((sc + '_live', {'show': show, 'ROW0': int(e['chr']), 'ROW1': int(e['racer'])}, -1))
            diffs['summary'] = compare(run / 'bonus_summary.png', overlay(parts))
    except Exception as x:   # нет снимка / пакета — провал ui с причиной
        diffs['error'] = (1e9, 0); lines.append('  (сравнение снимков: %s)' % x)
    okui = bool(ui) and all(e.get('ok') == '1' and e.get('screens') == '9' for _, e in ui) and \
        shown >= {'mmchar', 'mmtrack', 'pause', 'summary'} and \
        all(k in diffs and diffs[k][0] <= UI_TOL and diffs[k][1] >= 1500 for k in ('mmchar', 'mmtrack', 'pause', 'summary'))
    need('ui', okui, 'пакет %s, экраны из пакета %s, разница снимков с кадром пакета %s (допуск %.0f)' % (
        [e.get('ok') for _, e in ui][:3], sorted(shown), {k: (round(v[0], 1), v[1]) for k, v in diffs.items()}, UI_TOL))
    # ---- flyby
    import flyby_export as FB
    n, fps, rows_ = FB.frames()
    starts = [i for i, e in evs('start')]
    counts = [i for i, e in evs('count')]
    fly = evs('flyby'); fend = evs('flyby_end')
    per_race = []
    for k, s0 in enumerate(starts):
        nxt = starts[k + 1] if k + 1 < len(starts) else 10 ** 9
        f = [e for i, e in fly if s0 < i < nxt]; fe = [(i, e) for i, e in fend if s0 < i < nxt]; c = [i for i in counts if s0 < i < nxt]
        per_race.append(bool(f) and f[0].get('frames') == str(n) and bool(fe) and fe[0][1].get('skip') == '0' and
                        int(fe[0][1].get('shown', 0)) >= 60 and bool(c) and c[0] < fe[0][0])
    poses = {}
    for _, e in evs('flycam'):
        poses.setdefault(int(e['f']), [float(v) for v in e['eye'].split(',')])
    perr = max([float(np.abs(np.array(poses[f]) - rows_[f, :3]).max()) for f in poses] or [1e9])
    sh = {}
    for nm in ('bonus_flyby', 'bonus_top'):
        if (run / f'{nm}.png').exists():
            sh[nm] = np.asarray(Image.open(run / f'{nm}.png').convert('L'), np.float64)
    shot_ok = len(sh) == 2 and sh['bonus_flyby'].std() > 12 and float(np.abs(sh['bonus_flyby'] - sh['bonus_top']).mean()) > 15
    need('flyby', bool(per_race) and all(per_race) and set(poses) >= {0, 30, 60, 90, n - 1} and perr <= 0.01 and shot_ok,
         'гонок %d, облёт вместе с отсчётом %s, позы кадров %s расхождение с диском %.4f м, снимок облёта %s' % (
             len(starts), per_race, sorted(poses), perr,
             ('не вид сверху (разница %.0f)' % float(np.abs(sh['bonus_flyby'] - sh['bonus_top']).mean())) if len(sh) == 2 else 'нет'))
    # ---- measured native 3/2/1 cadence (do not infer from log wall timestamps)
    digit_runs = []
    for k, s0 in enumerate(starts):
        nxt = starts[k + 1] if k + 1 < len(starts) else 10 ** 9
        ds = [e for i,e in evs("countdigit") if s0 < i < nxt]
        expected = [0., 2.96, 3.96, 4.96]
        digit_runs.append(len(ds) == 4 and [int(e["digit"]) for e in ds] == [3,2,1,0] and
                          all(abs(float(e["elapsed"]) - want) <= .06 for e,want in zip(ds,expected)))
    need("countdown", bool(digit_runs) and all(digit_runs), "native 3/2/1/GO at 0/2.96/3.96/4.96s: %s" % digit_runs)
    # ---- music
    import sound_export as S
    alts = [Path(p).name for p in S.event_alts(1, 'SuperSprint')]
    mus = [e for _, e in evs('music')]
    bytrack = {}
    for e in mus:
        bytrack.setdefault(e.get('track'), set()).add(e.get('tune'))
    distinct = len(bytrack) >= 2 and len({next(iter(v)) for v in bytrack.values()}) == len(bytrack) and all(len(v) == 1 for v in bytrack.values())
    need('music', len(mus) >= 2 and all(e.get('tune') in alts and int(e.get('id', -1)) >= 0 for e in mus) and distinct,
         'трасса -> мелодия %s; альтернативы SuperSprint %s' % ({k: sorted(v) for k, v in bytrack.items()}, alts))
    # ---- race
    done = evs('done'); ex = evs('exit')
    need('race', bool(done) and any(e.get('ok') == '1' for _, e in ex) and len(menus) >= 2,
         'итог гонки %s, выходов %d, входов в главное меню %d' % (done[0][1] if done else 'нет', len(ex), len(menus)))
    if expect_fail:
        ok = {'ui', 'flyby', 'countdown', 'music'} <= set(errs)
        print(('OK красный пойман: ' if ok else 'FAIL красный НЕ пойман (нужны ui, flyby, music): ') + '; '.join(f'{k}: {v}' for k, v in errs.items()))
        print('\n'.join(lines)); return 0 if ok else 1
    print(('OK родные экраны, облёт, музыка заезда' if not errs else 'FAIL ' + '; '.join(f'{k}: {v}' for k, v in errs.items())) + f' · {run.name}')
    print('\n'.join(lines))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())

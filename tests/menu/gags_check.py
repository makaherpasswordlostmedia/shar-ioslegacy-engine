#!/usr/bin/env python3
"""№404 — разбор прогона сценок главного меню (tests/menu/gags.sh, сценарий tests/menu/gags_scenario.txt).

  gags_check.py RUN_DIR --fe FE [--expect-fail]

Ожидание — из данных диска, не из снимков: CPU-превью tools/frontend3d_export.py (та же камера меню, скиннинг и место
узла сцены, что у движка) даёт маску пикселей каждой сценки в её позе (fegagat из сценария). Снимок эмулятора проверяется
против снимка базы того же прогона (меню без сценки):
  * окно/комната: в маске сценки (расширенной на 3 px) отличается от базы >= HIT_MIN её пикселей, центр отличий — не дальше
    CENTER_PX от центра маски (сценка там, куда её ставит сцена диска: в окне / на полу);
  * Gag0 (Гомер меню играет отрезок gaghomer): в области «поза сценки минус поза покоя» (по превью) отличается >= HIT_MIN;
  * строки FEGAG start i=N forced=1 на каждую; расписание диска — первая сама (forced=0) через FIRST_S ± FIRST_TOL после входа в меню.
Код 0 — PASS. --expect-fail: код 0, только если проверка упала (красный контроль -DFE_GAGS_OLD=1 обязан падать)."""
import argparse, json, re, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import frontend3d_export as X  # noqa: E402

HIT_MIN = .35        # доля пикселей маски, где снимок отличается от базы (порог гейта)
DIFF = 24            # отличие пикселя, 0..255 по любому каналу
CENTER_PX = 14       # центр отличий от центра маски
FIRST_S, FIRST_TOL = 15.0, .6   # SLES_518.97 0x1b8180: первая сценка на 15000 мс; допуск — кадры + шаг сценария


def scenario(path):
    """[(номер, fegagat, fegagseg)] из сценария"""
    at, seg, out = None, None, []
    for ln in Path(path).read_text().splitlines():
        p = ln.split()
        if p[:2] == ['flag', 'fegagat']: at = float(p[2])
        elif p[:2] == ['flag', 'fegagseg']: seg = int(p[2])
        elif p[:2] == ['flag', 'fegag']: out.append((int(p[2]), at, seg))
    return out


def dilate(m, r=3):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--fe', required=True)
    ap.add_argument('--scn', default=str(ROOT / 'tests/menu/gags_scenario.txt')); ap.add_argument('--expect-fail', action='store_true')
    a = ap.parse_args(); run = Path(a.run); errs = []; lines = []
    log = (run / 'smoke.txt').read_text(errors='replace') if (run / 'smoke.txt').exists() else ''
    fe = X.read_fe(a.fe)
    if len(fe['gags']) != 8: errs.append(f"в fe.shr таблица GAG1 из {len(fe['gags'])} сценок, ждём 8 (страница 3dFEGags.pag)")
    base = np.asarray(Image.open(run / 'gag_base.png').convert('RGB')).astype(int) if (run / 'gag_base.png').exists() else None
    if base is None: errs.append('нет снимка gag_base')
    st0 = {}; X.preview(a.fe, None, 4, stats_out=st0); idle = st0['homer_mask']
    for i, at, seg in scenario(a.scn):
        if not re.search(rf'^FEGAG start i={i} \S+ forced=1', log, re.M): errs.append(f'сценка {i}: нет строки FEGAG start forced=1')
        f = run / f'gag_{i}.png'
        if base is None or not f.exists() or i >= len(fe['gags']): errs.append(f'сценка {i}: нет снимка'); continue
        shot = np.asarray(Image.open(f).convert('RGB')).astype(int)
        st = {}; X.preview(a.fe, None, 4, gag=i, gag_t=at, stats_out=st)
        if fe['gags'][i]['flags'] & X.GAG_ONHOMER: mask = st['homer_mask'] & ~dilate(idle, 2); what = 'Гомер меню: поза сценки минус покой'
        else: mask = st['gag_mask']; what = 'сценка'
        if mask.sum() < 80: errs.append(f'сценка {i}: по данным в кадре меню почти не видна ({int(mask.sum())} пикс.)'); continue
        dm = dilate(mask); diff = np.abs(shot - base).max(2) > DIFF
        hit = float((diff & mask).sum()) / mask.sum()
        ys, xs = np.nonzero(diff & dm); my, mx = np.nonzero(mask)
        dc = float(np.hypot(xs.mean() - mx.mean(), ys.mean() - my.mean())) if len(xs) else 1e9
        ok = hit >= HIT_MIN and dc <= CENTER_PX
        lines.append(f"  {i} {fe['gags'][i]['name']:9s} t={at:.1f}{'' if seg is None or i else f' отрезок {seg}'}: {what} {int(mask.sum())} пикс., "
                     f"отличается от базы {hit * 100:.0f} %, центр {dc:.1f} px {'OK' if ok else 'МИМО'}")
        if not ok: errs.append(f'сценка {i}: {hit * 100:.0f} % маски, центр {dc:.1f} px')
    menu = re.search(r'^MENU n=1 t=([\d.]+)', log, re.M)
    auto = re.search(r'^FEGAG start i=(\d+) name=(\S+) forced=0 .* t=([\d.]+)', log, re.M)
    if not menu or not auto: errs.append('расписание: нет строки MENU или первой сценки forced=0')
    else:
        dt = float(auto.group(3)) - float(menu.group(1))
        lines.append(f"  расписание: первая сама — {auto.group(2)} через {dt:.1f} с после входа в меню (диск: {FIRST_S:.0f} с)")
        if abs(dt - FIRST_S) > FIRST_TOL: errs.append(f'первая сценка через {dt:.1f} с, ждём {FIRST_S:.0f}')
    fl = re.search(r'^FE n=\d+ .*bytes=(\d+)', log, re.M)
    if fl: lines.append(f"  куча гостиной (feStats.bytes): {int(fl.group(1)) / 1048576:.2f} МБ")
    res = 'PASS' if not errs else 'FAIL ' + '; '.join(errs[:6])
    print(res + f' · tests/menu/gags_check.py {run.name}'); print('\n'.join(lines))
    if a.expect_fail: return 0 if errs else 1
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Разбор прогона tests/idle/scenario.txt (tools/smoke.sh): простой меню -> титульный -> ролик простоя -> кнопка -> меню.

    python tests/idle/check.py build/smoke/<время> [--copy DIR] [--expect-fail K1,K2]

Правка Роба 33 (остаток): «титульный — как в оригинале, когда долго никто не играет (демо/заставка простоя)».
Данные: movies\\demo.rmv (нарезка игры 64 с), экран Demo.scr frontend.p3d («- DEMO -»), SLES_518.97 (CGuiScreenDemo).
  [demo_flow]   порядок строк: TITLE on -> DEMO on -> DEMO off -> TITLE off from=demo -> MENUBACK
  [demo_idle]   ролик начался через demoidle (2 с сценария) после титульного: DEMO_LO..DEMO_HI с
  [demo_play]   ролик шёл: показано не меньше MIN_SHOWN кадров, ошибок нет, не доигран (прерван кнопкой)
  [demo_frame]  снимок окна = тот же кадр demo.rmv, разжатый ffmpeg (отпечаток окна рамки, как tools/intro_check.py);
                контроль — другой кадр ролика обязан разойтись
  [demo_label]  надпись «- DEMO -» на экране: в её пикселях снимок ближе к макету с надписью, чем без неё
  [demo_return] любая кнопка — меню: DEMO off по кнопке с первого нажатия, отклик до кадра меню (MENUBACK) ≤ LAT_MS
--expect-fail — отрицательный прогон (flag demodeaf / demonolabel): код 0, если все названные ключи провалились."""
import argparse, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import movie_export as mx  # noqa: E402
import intro_check as ic  # noqa: E402  (снимок окна и отпечаток окна рамки — как у интро)

DEMO_LO, DEMO_HI = 1.7, 3.2      # сценарий: demoidle 2 с
MIN_SHOWN = 25
LAT_MS = 300
TOL = ic.TOL


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def label_layers():
    """надпись «- DEMO -» RGBA из свежей выгрузки boot.shr (tools/load_export.py); рамки поверх ролика нет (правка 49)"""
    import load_export as LX
    with tempfile.TemporaryDirectory() as t:
        res = LX.export('boot', out=str(Path(t) / 'boot.shr'), mocks=False)
    return LX.mock(res, 'demo', {}, bg=(0, 0, 0, 0)).convert('RGBA')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--copy'); ap.add_argument('--expect-fail', default='')
    a = ap.parse_args(); run = Path(a.run)
    lines = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    bad, info, keyed = [], [], set()
    def fail(k, msg): bad.append(f'[{k}] {msg}'); keyed.add(k)
    seq = []
    for l in lines:
        w = l.split()
        if not w: continue
        if w[0] == 'TITLE' and len(w) > 1: seq.append(('TITLE_' + w[1].upper(), kv(l)))
        elif w[0] in ('DEMO', 'MENUBACK', 'DEMOSHOT'): seq.append(((w[0] + ('_' + w[1].upper() if w[0] == 'DEMO' else '')), kv(l)))
    names = [s[0] for s in seq]
    info.append('строки: ' + ' -> '.join(names))
    want = ['TITLE_ON', 'DEMO_ON', 'DEMO_OFF', 'TITLE_OFF', 'MENUBACK']
    pos, ok = 0, True
    for n in names:
        if pos < len(want) and n == want[pos]: pos += 1
    if pos < len(want): fail('demo_flow', 'нет цепочки ' + ' -> '.join(want) + f' (дошла до {want[pos]})')
    g = lambda n: next((d for k, d in seq if k == n), None)
    t_on, d_on, d_off, t_off, back = g('TITLE_ON'), g('DEMO_ON'), g('DEMO_OFF'), g('TITLE_OFF'), g('MENUBACK')
    if t_on and d_on:
        dt = float(d_on['t']) - float(t_on['t']); info.append(f'титульный -> ролик через {dt:.1f} с')
        if not DEMO_LO <= dt <= DEMO_HI: fail('demo_idle', f'ролик начался через {dt:.1f} с после титульного (ждём {DEMO_LO}..{DEMO_HI})')
    elif not d_on: fail('demo_idle', 'ролик простоя не начался (нет DEMO on; нет movies/demo.smv?)')
    if any(k == 'DEMO_NONE' for k in names): fail('demo_play', 'ролика нет: ' + str(g('DEMO_NONE')))
    if d_off:
        info.append(f"ролик: показано {d_off['shown']} пропущено {d_off['dropped']} тишина {d_off['under']} ошибка {d_off['err']} "
                    f"конец={d_off['end']} {d_off['ms']} мс")
        if int(d_off['err']) or int(d_off['shown']) < MIN_SHOWN or d_off['end'] != '0':
            fail('demo_play', f"ролик не шёл как надо: показано {d_off['shown']} (≥ {MIN_SHOWN}), ошибка {d_off['err']}, доигран={d_off['end']}")
        if d_off['key'] in ('0x0', '0') or int(d_off['presses']) != 1 or not 0 <= float(d_off['lat_ms']) <= LAT_MS:
            fail('demo_return', f"ролик ушёл не с первого нажатия / поздно: key={d_off['key']} нажатий {d_off['presses']} отклик {d_off['lat_ms']} мс")
    else: fail('demo_return', 'ролик не ушёл по нажатию (нет DEMO off) — из простоя нет возврата в меню')
    if t_off and t_off.get('from') != 'demo': fail('demo_return', f"титульный закрыт не из ролика (from={t_off.get('from')})")
    if back:
        info.append(f"кнопка -> кадр меню: {back['lat_ms']} мс (≤ {LAT_MS})")
        if not 0 <= float(back['lat_ms']) <= LAT_MS: fail('demo_return', f"меню через {back['lat_ms']} мс после нажатия (> {LAT_MS})")
    elif d_off: fail('demo_return', 'нет MENUBACK — кадра меню после ролика')
    shots = [d for k, d in seq if k == 'DEMOSHOT']
    if not shots: fail('demo_frame', 'нет снимка ролика (DEMOSHOT)')
    for s in shots[:1]:
        p = run / f"{s['name']}.png"; f = int(s['frame'])
        if not p.exists() or f < 0: fail('demo_frame', f'нет снимка {p.name} или кадра'); continue
        got = ic.window_frame(p); ref = mx.reference_frame('demo', f); nf = (f + 800) % 1500
        neg = mx.reference_frame('demo', nf)
        d0 = float(np.abs(ic.thumb(got) - ic.thumb(ref)).mean()); dn = float(np.abs(ic.thumb(got) - ic.thumb(neg)).mean())
        info.append(f'снимок кадра {f}: разница с ffmpeg {d0:.2f} (≤ {TOL}); контроль кадр {nf}: {dn:.2f} (> {TOL})')
        if d0 > TOL: fail('demo_frame', f'снимок != кадру {f} demo.rmv ({d0:.2f} > {TOL})')
        if dn <= TOL: fail('demo_frame', f'контроль не различим ({dn:.2f} ≤ {TOL}) — сверка слепая')
        lab = label_layers()
        without = Image.fromarray(np.asarray(ref, np.uint8)).convert('RGBA'); with_ = Image.alpha_composite(without, lab)
        m = np.asarray(lab)[..., 3] > 0; g_ = np.asarray(got, np.float32)
        dw = float(np.abs(g_ - np.asarray(with_.convert('RGB'), np.float32))[m].mean())
        dwo = float(np.abs(g_ - np.asarray(without.convert('RGB'), np.float32))[m].mean())
        info.append(f'надпись «- DEMO -» ({int(m.sum())} пикс.): разница с макетом с надписью {dw:.1f}, без неё {dwo:.1f}')
        if not dw < dwo: fail('demo_label', f'надписи «- DEMO -» на экране нет (с ней {dw:.1f} ≥ без неё {dwo:.1f})')
        if a.copy:
            Path(a.copy).mkdir(parents=True, exist_ok=True); got.save(Path(a.copy) / 'idle_demo.png'); with_.save(Path(a.copy) / 'idle_demo_mock.png')
    if a.expect_fail:
        want_k = [k for k in a.expect_fail.split(',') if k]; miss = [k for k in want_k if k not in keyed]
        print(('idle: КРАСНЫЙ как надо — пойманы ' + ', '.join(want_k)) if not miss else 'idle: НЕ КРАСНЫЙ — не пойманы ' + ', '.join(miss))
        for b in bad: print('  - ' + b)
        return 0 if not miss else 1
    print(('idle: FAIL — ' + '; '.join(bad)) if bad else 'idle: PASS — простой: меню -> титульный -> ролик «- DEMO -» -> кнопка -> меню')
    for i in info: print('  ' + i)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

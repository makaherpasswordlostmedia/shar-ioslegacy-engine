#!/usr/bin/env python3
"""Разбор прогона tests/boot_flow/scenario.txt (tools/smoke.sh): простой меню -> ирис -> титульный -> ролик простоя ->
кнопка -> ирис -> меню -> NEW GAME -> газета -> ролик fmv1a -> игра. Правки Роба 01.10:
  [demo_tv]     153: ролик простоя без рамки-телевизора — углы снимка demo не цвета рамки меню
  [iris_in]     154: простой меню -> титульный: ирис закрывается (IRIS why=title_in phase=close, кадров >= MIN_FRAMES) до TITLE on
  [iris_exit]   154: кнопка в ролике простоя -> ирис закрывается над ним (why=demo phase=close: кадров >= MIN_FRAMES, отверстие
                только сужается) после TITLE off, потом раскрывается над меню (phase=open, кадров >= MIN_FRAMES, done) — не резкий срез
  [music]       155: NEW GAME — звук уровня после газеты и ролика: между MENUGO и концом ролика (MSNFMV name=fmv1a) ни один
                поток музыки/атмосферы уровня не запущен (STREAM … held=0, кроме стингеров меню), LEVELAUDIO — после MSNFMV
    python tests/boot_flow/check.py RUN_DIR [--expect-fail k1,k2]   # код 0 = OK (или все названные ключи упали)"""
import argparse, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

MIN_FRAMES = 10                   # ирис — анимация, не срез: кадров закрытия/раскрытия не меньше (0,65 с при 60 Гц ~ 39)
FE_STINGERS = ('newspaper_spin', 'loading_screen', 'simpsons_theme')   # музыка меню и газеты (правки 20, 134) — не звук уровня
KEYS = ('demo_tv', 'iris_in', 'iris_exit', 'music')


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--expect-fail', default='')
    a = ap.parse_args(); run = Path(a.run)
    L = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    bad, info, keyed = [], [], set()
    def fail(k, msg): bad.append(f'[{k}] {msg}'); keyed.add(k)
    idx = lambda pfx, i0=0, cond=lambda d: True: next((i for i in range(i0, len(L)) if L[i].startswith(pfx) and cond(kv(L[i]))), None)
    # [demo_tv]
    p = run / 'demo.png'
    if not p.exists(): fail('demo_tv', 'нет снимка demo')
    else:
        import intro_check as ic, ui_export as U
        got = np.asarray(ic.window_frame(p), np.float32)
        tv = np.asarray(U.widescreen_tvframe(U.all_images()['tvframe.png'], U.DST_W, U.DST_H, U.S).convert('RGBA'), np.float32)
        d = [float(np.abs(got[y:y + 6, x:x + 6] - tv[y:y + 6, x:x + 6, :3]).mean()) for y, x in ((2, 2), (2, 472), (264, 2), (264, 472))]
        info.append('углы снимка demo против рамки меню: ' + ', '.join(f'{v:.0f}' for v in d) + ' (рамка — все < 25)')
        if all(v < 25 for v in d): fail('demo_tv', 'ролик простоя в рамке-телевизоре')
    # [iris_in]
    t_on = idx('TITLE on')
    if t_on is None: fail('iris_in', 'титульного не было (нет TITLE on)')
    else:
        n = sum(1 for l in L[:t_on] if l.startswith('IRIS why=title_in phase=close'))
        info.append(f'ирис меню -> титульный: кадров закрытия {n}')
        if n < MIN_FRAMES: fail('iris_in', f'простой меню -> титульный без ириса (кадров закрытия {n})')
    # [iris_exit]
    t_off = idx('TITLE off')
    if t_off is None: fail('iris_exit', 'нет TITLE off')
    else:
        why = kv(L[t_off]).get('from', 'title')
        cl = [kv(l) for l in L[t_off:] if l.startswith(f'IRIS why={why} phase=close')]
        op = [kv(l) for l in L[t_off:] if l.startswith(f'IRIS why={why} phase=open')]
        done = idx(f'IRIS why={why} phase=done', t_off)
        rs = [float(c['r']) for c in cl]
        info.append(f'ирис выхода ({why}): закрытие {len(cl)} кадров r {rs[0] if rs else "-"} -> {rs[-1] if rs else "-"}, раскрытие {len(op)}, done={done is not None}')
        if len(cl) < MIN_FRAMES: fail('iris_exit', f'выход с {why} в меню без ириса (кадров закрытия {len(cl)})')
        elif any(b > a_ + 1e-3 for a_, b in zip(rs, rs[1:])): fail('iris_exit', 'отверстие ириса не только сужается')
        if len(op) < MIN_FRAMES or done is None: fail('iris_exit', f'меню не раскрылось ирисом (кадров {len(op)}, done={done is not None})')
        mb = idx('MENUBACK', t_off)
        if mb is not None: info.append('MENUBACK ' + ' '.join(f'{k}={v}' for k, v in kv(L[mb]).items()))
    # [music]
    go = idx('MENUGO'); fe = idx('MSNFMV', 0, lambda d: d.get('name') == 'fmv1a'); la = idx('LEVELAUDIO')
    if go is None or fe is None: fail('music', f'нет NEW GAME или ролика fmv1a (MENUGO {go}, MSNFMV {fe})')
    else:
        early = [l for l in L[go:fe] if l.startswith('STREAM ') and kv(l).get('held') == '0'
                 and not kv(l).get('track', '-').startswith(FE_STINGERS) and kv(l).get('track') != '-']
        held = [l for l in L[go:fe] if l.startswith('STREAM ') and kv(l).get('held') == '1']
        info.append(f'до конца ролика: запущено потоков уровня {len(early)}, удержано {len(held)}; LEVELAUDIO строка {la}, MSNFMV {fe}')
        for l in early[:3]: info.append('  рано: ' + l)
        if early: fail('music', f'звук уровня до конца ролика: {kv(early[0]).get("s")} {kv(early[0]).get("track")}')
        if la is None or la < fe: fail('music', 'LEVELAUDIO (туба/атмосфера уровня) не после ролика')
    if not any(l.startswith('END') for l in L): fail('flow', 'нет END')
    exp = [k for k in a.expect_fail.split(',') if k]
    if exp:
        miss = [k for k in exp if k not in keyed]
        print('boot_flow (красный): ' + ('PASS — упали ' + ', '.join(exp) if not miss else 'FAIL — не упали ' + ', '.join(miss)))
        for x in bad + info: print('  ' + x)
        return 1 if miss else 0
    print('boot_flow: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(bad)))
    for x in info: print('  ' + x)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

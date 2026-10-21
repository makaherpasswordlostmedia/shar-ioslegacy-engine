#!/usr/bin/env python3
"""Правка Роба 293: разбор части M10 тура TEST 10 (tests/fe_guard/psp_test10_menu.txt) — четыре настоящих перелёта NEW GAME.
  python3 tests/fe_guard/test10_read.py ПАПКА_ТУРА [--sheet OUT.png]
ПАПКА_ТУРА — build/psp-tour/<время> (smoke.txt и shots/ с PSP) или папка прогона эмулятора (сухой прогон).
По сценам M10a..M10d: строки FEFLY (кадров, опоздали, ждали, прежнее), какие кадры перелёта (tl) шли после опоздавшей смены
(поле sw=строка луча,опоздала,ждали,guard у FEFR), длительность кадров dt; SWAPFLAG — счётчики (game_late — опоздания в городе,
там правило пока не действует); кадры fecap (shots/fe293_<кадр перелёта>_<tl×100>.bmp) — лист и перепад яркости низа экрана
(пол) от кадра к кадру: всплеск = «мигание» в готовом кадре (тогда причина не в смене буфера, а в самом кадре).
Что значит ответ: в b (как было) мигание есть, в a нет — правка помогла; какая из двух — по c/d и опозданиям: в c пол мигает весь
перелёт и это «то самое», в d нет — смена буфера (2); в c мигания нет — механизма (2) на железе нет, помогло угасание подсветки (1);
опозданий нет, а мигание в a осталось — причина другая (смотреть кадры fecap). Строка «подсветка» — сколько кадров подсветка гасла."""
import re, sys, glob, os
from pathlib import Path


def kv(line):
    return dict(re.findall(r'(\w+)=([^\s]+)', line))


def main():
    d = Path(sys.argv[1]); smk = (d / 'smoke.txt').read_text(errors='replace').splitlines()
    scene = '-'; parts = {}
    for l in smk:
        if l.startswith('SCENE '): scene = l.split()[1]; continue
        if not scene.startswith('M10'): continue
        p = parts.setdefault(scene, dict(fr=[], fly=[], flag=[], cap=[]))
        if l.startswith('FEFR '): p['fr'].append(kv(l))
        elif l.startswith('FEFLY ') and 'item=4' in l and 'mode=0' in l: p['fly'].append(kv(l))
        elif l.startswith('SWAPFLAG '): p['flag'].append(kv(l))
        elif l.startswith('FECAP '): p['cap'].append(l)
    if not parts: print('нет сцен M10 в smoke.txt (часть не дошла или тур без --test10)'); return 1
    for sc in sorted(parts):
        p = parts[sc]
        print(f'== {sc}')
        for f in p['fly']:
            print(f"  FEFLY: кадров {f.get('swaps', '?')}, опоздали {f.get('late', '?')}, ждали {f.get('waited', '?')}, прежнее={f.get('old', '?')}, {f.get('s', '?')} с")
        fly = [f for f in p['fr'] if f.get('home') == '0' or float(f.get('tl', '0')) < 300]
        late = []
        for f in fly:
            sw = f.get('sw', '').split(',')
            if len(sw) == 4 and sw[3] == '1' and sw[1] == '1': late.append(f"{float(f['tl']):.1f}{'(ждали)' if sw[2] == '1' else ''}")
        dts = [float(f.get('dt', 0)) for f in fly if float(f.get('dt', 0)) > 0]
        menu = [i for i, f in enumerate(p['fr']) if f.get('home') == '1' and float(f.get('tl', '0')) < 300]
        if menu:   # подсветка пункта после ухода из главного вида: кадров с прежним числом подсветок (bills)
            i0 = menu[-1]; nb = p['fr'][i0].get('bills'); n = 0; dur = 0.
            for f in p['fr'][i0 + 1:]:
                if f.get('home') != '0' or f.get('bills') != nb: break
                n += 1; dur += float(f.get('dt', 0)) / 1000.
            print(f'  подсветка пункта после старта: {n} кадров, {dur:.2f} с (у оригинала 0,16 с; 0 — пропала за кадр, как было)')
        print(f"  кадров перелёта {len(fly)}; dt мс: мин {min(dts) if dts else 0:.1f}, макс {max(dts) if dts else 0:.1f}; после опоздавшей смены: "
              f"{', '.join(late) if late else 'нет'}")
        if p['flag']: f = p['flag'][-1]; print(f"  счётчики с начала запуска (на входе в сцену): смен {f.get('n')}, опоздали {f.get('late')}, ждали {f.get('waited')}, "
                                               f"в городе опоздали {f.get('game_late')}")
        done = [c for c in p['cap'] if c.startswith('FECAP done') or c.startswith('FECAP nomem')]
        if done: print('  ' + done[-1])
    fs = sorted(glob.glob(str(d / 'shots' / 'fe293_*.bmp')))
    if fs:
        import numpy as np
        from PIL import Image
        prev = None; rows = []
        for f in fs:
            a = np.asarray(Image.open(f).convert('RGB')).astype(float)
            low = a[150:250, 40:440].mean()   # низ экрана внутри рамки — пол
            rows.append((os.path.basename(f), low, 0. if prev is None else low - prev)); prev = low
        print(f'кадры fecap: {len(fs)}; яркость низа экрана и перепад к прошлому кадру (всплеск > 12 — подозрение на мигание в готовом кадре):')
        for n, lo, dl in rows: print(f"  {n}  {lo:6.1f}  {dl:+6.1f}{'  <<<' if abs(dl) > 12 else ''}")
        if '--sheet' in sys.argv:
            out = sys.argv[sys.argv.index('--sheet') + 1]; W, H = 240, 136; n = len(fs); cols = 7
            sheet = Image.new('RGB', (W * cols, H * ((n + cols - 1) // cols)))
            for k, f in enumerate(fs): sheet.paste(Image.open(f).convert('RGB').resize((W, H)), ((k % cols) * W, (k // cols) * H))
            sheet.save(out); print('лист:', out)
    else: print('кадров fecap нет (shots/fe293_*.bmp)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Правка Роба 325: разбор части M11 тура (tests/fe_guard/psp_test11_menu.txt) — два настоящих перелёта NEW GAME на PSP:
M11a прежнее (flag febillold 1, кадры shots/fe3250_*.bmp) и M11b новое (срез подсветок по полосе, fe3251_*.bmp).
  python3 tests/fe_guard/test11_read.py ПАПКА_ТУРА [--fe build/fe.shr] [--sheet OUT.png]
ПАПКА_ТУРА — build/psp-tour/<время> (smoke.txt и shots/ с PSP) или папка прогона безголового эмулятора (сухой прогон гейта
tests/fe_guard/gate325.sh: программная отрисовка PPSSPP выбрасывает треугольник за полосой так же, как железо; оконный эмулятор
рисует всё — у него оба перелёта одинаковые).
По перелёту: строки FEFLY, по кадрам FEFR — bn (подсветок не целиком в пирамиде защитной полосы), bc (из них нарезано движком);
по кадрам fecap: яркость низа экрана (пол у газеты) и скачок к прошлому кадру; сверка кадра с моделью (tests/fe_guard/ge325.py):
пол + подсветки «железо» (полоса GE выбрасывает треугольник) против «эмулятор» (нарисовано всё).
Что значит ответ на железе: в M11a кадры после tl ~35 совпадают с «железо» и пол темнеет скачком (как TEST 10: 103 → 69) —
причина подтверждена; в M11b совпадают с «эмулятор/обе», скачка нет — правка помогла."""
import argparse, glob, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ge325 as G

ROOT = Path(__file__).resolve().parents[2]


def kv(line):
    return dict(re.findall(r'(\w+)=([^\s]+)', line))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--fe', default=str(ROOT / 'build/fe.shr')); ap.add_argument('--sheet')
    a = ap.parse_args(); d = Path(a.dir)
    smk = (d / 'smoke.txt').read_text(errors='replace').splitlines() if (d / 'smoke.txt').exists() else []
    scene = '-'; parts = {}
    for l in smk:
        if l.startswith('SCENE '): scene = l.split()[1]; continue
        if not scene.startswith('M11'): continue
        p = parts.setdefault(scene, dict(fr=[], fly=[], cap=[]))
        if l.startswith('FEFR '): p['fr'].append(kv(l))
        elif l.startswith('FEFLY ') and 'item=4' in l and 'mode=0' in l: p['fly'].append(kv(l))
        elif l.startswith('FECAP '): p['cap'].append(l)
    if not parts: print('нет сцен M11 в smoke.txt (часть не дошла или тур без неё)')
    for sc in sorted(parts):
        p = parts[sc]; fly = [f for f in p['fr'] if f.get('home') == '0']
        print(f'== {sc}')
        for f in p['fly']: print(f"  FEFLY: кадров {f.get('swaps', '?')}, {f.get('s', '?')} с")
        risk = [f"{float(f['tl']):.1f}" for f in fly if int(f.get('bn', 0)) > 0]
        cut = sum(int(f.get('bc', 0)) for f in fly); need = sum(int(f.get('bn', 0)) for f in fly)
        print(f'  кадров перелёта {len(fly)}; подсветок не целиком в пирамиде полосы (bn) всего {need}, нарезано (bc) {cut}'
              + (f"; кадры с bn > 0: {', '.join(risk[:12])}{' …' if len(risk) > 12 else ''}" if risk else ''))
        if fly and 'bn' not in fly[0]: print('  (в строках FEFR нет bn/bc — EBOOT без правки 325)')
        done = [c for c in p['cap'] if c.startswith('FECAP done') or c.startswith('FECAP nomem')]
        if done: print('  ' + done[-1])
    F = G.FE(a.fe); res = {}
    for tag, lab in (('3250', 'M11a прежнее'), ('3251', 'M11b новое')):
        fs = sorted(glob.glob(str(d / 'shots' / f'fe{tag}_*.bmp')), key=lambda s: int(re.search(r'_(\d+)_\d{4}\.bmp$', s).group(1)))
        if not fs: print(f'{lab}: кадров fe{tag}_*.bmp нет'); continue
        print(f'{lab}: кадров fecap {len(fs)}; яркость низа экрана, скачок к прошлому кадру (> 12 — подозрение), сверка с моделью '
              '(ошибка: только пол | «железо» | «эмулятор»)')
        prev = None; pk = -9; jumps = []; late_hw = late_emu = 0; rows = []
        for fn in fs:
            k = int(re.search(r'_(\d+)_\d{4}\.bmp$', fn).group(1))
            tl, e, low = G.frame_models(F, fn); dl = 0. if prev is None or k != pk + 1 else low - prev; prev = low; pk = k   # скачок — только между соседними кадрами
            v = G.verdict(e)
            if abs(dl) > 12 and tl > 20: jumps.append((tl, dl))
            if tl >= 35 and v == 'железо': late_hw += 1
            if tl >= 35 and v in ('эмулятор', 'обе'): late_emu += 1
            es = '   -' if e is None else f'{e[0]:5.1f} | {e[1]:5.1f} | {e[2]:5.1f}'
            print(f"  {os.path.basename(fn):20s} k={k:2d} tl {tl:5.2f}  низ {low:6.1f} {dl:+6.1f}{'  <<<' if abs(dl) > 12 and tl > 20 else '     '}  {es}  {v}")
            rows.append(fn)
        res[tag] = dict(jumps=jumps, late_hw=late_hw, late_emu=late_emu, files=rows)
        print(f'  итог {lab}: скачков яркости пола после tl 20: {len(jumps)}' + (' (' + ', '.join(f'tl {t:.1f}: {x:+.0f}' for t, x in jumps) + ')' if jumps else '')
              + f'; кадров после tl 35: как «железо» (свет выброшен) {late_hw}, как «всё нарисовано» {late_emu}')
    if '3250' in res and '3251' in res:
        o, n = res['3250'], res['3251']
        if o['late_hw'] and not n['late_hw'] and not n['jumps']: print('ВЫВОД: прежнее теряет свет из окна (как TEST 10), новое — нет: правка 325 помогла в этом прогоне (тур — железо, сухой прогон — программный эмулятор)')
        elif not o['late_hw'] and not n['late_hw']: print('ВЫВОД: оба перелёта рисуют всё (эмулятор или железо не теряет) — сравнить глазами')
        else: print('ВЫВОД: новое всё ещё теряет свет или скачет — смотреть кадры fe3251_*')
    if a.sheet and res:
        from PIL import Image
        W, H = 240, 136; cols = max(len(r['files']) for r in res.values())
        sheet = Image.new('RGB', (W * cols, H * len(res)))
        for j, tag in enumerate(sorted(res)):
            for k, fn in enumerate(res[tag]['files']): sheet.paste(Image.open(fn).convert('RGB').resize((W, H)), (k * W, j * H))
        sheet.save(a.sheet); print('лист (строка 1 — прежнее, 2 — новое):', a.sheet)
    return 0


if __name__ == '__main__':
    sys.exit(main())

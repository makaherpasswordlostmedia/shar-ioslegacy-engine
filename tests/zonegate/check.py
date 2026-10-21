#!/usr/bin/env python3
"""Гейт правки 181 (подгрузка воротами оригинала): путь бота оригинала (прогоны близнецов b2_loop, b2_loop2 — своя езда в PCSX2)
через ворота порта (viewer/zonegate.h, данные GAT1 из tools/regions_export.py) даёт те же загрузки файлов зон, что прочитал
оригинал: каждое чтение файла зоны оригиналом (вспышка чтений, build/twins/b2/<прогон>/reads.tsv) — загрузка этого региона
портом в ±1,2 с; лишних загрузок у порта нет. Красный: -DZG_PLANT_SHIFT (ворота сдвинуты на 40 м) обязан упасть.
  python3 tests/zonegate/check.py   -> PASS/FAIL, build/zonegate/*.txt"""
import re, subprocess, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import regions_export as RX
OUT = ROOT / 'build/zonegate'; OUT.mkdir(parents=True, exist_ok=True)
RUNS = ('b2_loop', 'b2_loop2')
WIN = 60   # кадров (50 к/с): ±1,2 с


class R(RX.Regions):
    def __init__(self): self.level = 1; self.names = RX.level_regions(1)


def orig_loads(run):
    """вспышки чтений каждого файла зоны: новая, если пауза > 200 кадров -> [(кадр, регион)]"""
    last, out = {}, []
    for l in (ROOT / f'build/twins/b2/{run}/reads.tsv').read_text().splitlines()[1:]:
        c = l.split('\t'); fr = int(float(c[0]))
        for f in c[4].split(' | '):
            m = re.search(r'art/(l1[zr]\w*)\.p3d$', f)
            if not m: continue
            r = m.group(1)
            if r not in last or fr - last[r] > 200: out.append((fr, r))
            last[r] = fr
    return out


def port_loads(binp, run, names):
    o = subprocess.run([str(binp), str(OUT / 'gat1.bin'), str(ROOT / f'build/twins/o4/{run}/drive.tsv')], capture_output=True, text=True).stdout
    ev, start = [], 0
    for l in o.splitlines():
        p = l.split()
        if p[0] == 'START': start = int(p[2], 16)
        elif p[0] == 'EV':
            fr, b, a = int(p[1]), int(p[3], 16), int(p[4], 16)
            for i, n in enumerate(names):
                if (a >> i & 1) and not (b >> i & 1): ev.append((fr, n))
    return ev, start


def judge(binp, names):
    lines, bad = [], 0
    for run in RUNS:
        O = orig_loads(run); P, start = port_loads(binp, run, names)
        used = set()
        for fr, r in O:
            hit = [i for i, (pf, pr) in enumerate(P) if pr == r and abs(pf - fr) <= WIN and i not in used]
            if hit: used.add(hit[0]); lines.append(f'{run} {r} оригинал {fr} порт {P[hit[0]][0]} OK')
            else: bad += 1; lines.append(f'{run} {r} оригинал {fr} порт — НЕТ')
        for i, (pf, pr) in enumerate(P):
            if i not in used: bad += 1; lines.append(f'{run} {pr} порт {pf} — ЛИШНЯЯ (оригинал не читал)')
        lines.append(f'{run}: старт порта {start:04x}, загрузок оригинала {len(O)}, порта {len(P)}')
    return bad, lines


def main():
    names = RX.level_regions(1)
    (OUT / 'gat1.bin').write_bytes(R().gat1())
    inc = ['-I', str(ROOT / 'viewer')]
    for nm, flags in (('red', ['-DZG_PLANT_SHIFT']), ('green', [])):
        subprocess.run(['cc', '-std=c99', '-O2', *inc, *flags, str(ROOT / 'tests/zonegate/host.c'), '-lm', '-o', str(OUT / nm)], check=True)
    rb, rl = judge(OUT / 'red', names); gb, gl = judge(OUT / 'green', names)
    (OUT / 'red.txt').write_text('\n'.join(rl) + '\n'); (OUT / 'green.txt').write_text('\n'.join(gl) + '\n')
    print('\n'.join(gl[-2:]))
    if rb == 0: print('КРАСНЫЙ НЕ ПОЙМАН: сдвинутые ворота прошли'); return 1
    print(f'красный (ворота +40 м): {rb} расхождений — упал, как должен')
    print(('PASS' if gb == 0 else 'FAIL') + f': зелёный — расхождений {gb} (build/zonegate/green.txt)')
    return 0 if gb == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

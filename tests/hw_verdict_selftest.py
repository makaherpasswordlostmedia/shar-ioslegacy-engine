#!/usr/bin/env python3
"""Красный контроль tools/hw_verdict.py: синтетический журнал, где каждая сцена должна получить заранее известный вердикт.
Гейт, который не умеет краснеть, ничего не доказывает — здесь проверяется, что вердикт краснеет на каждый вид дефекта и остаётся зелёным на чистом.
python3 tests/hw_verdict_selftest.py  -> код 0 если все 18 ожиданий совпали"""
import subprocess, sys, tempfile, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def stat(n, frames=300, p95=27.0, p99=29.0, mx=31.0, missed=2, mv=0, mvmax=0, memfail=0, heap=10):
    return f'STAT {n} frames {frames} p95 {p95} p99 {p99} max {mx} per 2 missed {missed} missvis {mv} missvismax {mvmax} readerr 0 allocfail 0 heapmin {heap} settle 0.5 gepeak 40 geskip 0 memfail {memfail} blkmin 8 gebad 0'

def slow(t, work, io, n): return f'SLOWFRAME t={t:.2f} work={work} io={io} cpu={work+io} logic=8 per=2 scene={n} marks 0:0.1'

def row(t, n, mv): return f'{t:.1f} {n} 28.0 20.00 30.00 20.00 20000 300 4.00 long 0 {mv} 0 0 16.00 st=game rec=0'

def build():
    L = []; t = 10.0
    def scene(n):
        nonlocal t; L.append(f'SCENE {n} {t:.1f}'); t0 = t; t += 10; return t0
    # 1 чистая -> ЗЕЛЁНЫЙ
    n = 'ok_drive'; scene(n); L += [stat(n)]
    # 2 тяжёлая: p95 38, 20 % пропусков, без io -> КРАСНЫЙ
    n = 'slow_drive'; t0 = scene(n); L += [slow(t0 + 1 + i * .05, 36, 0.0, n) for i in range(40)] + [stat(n, 200, 38, 42, 50, 40)]
    # 3 один кадр 90 мс под записью журнала 45 мс -> ЗЕЛЁНЫЙ*
    n = 'io_spike'; t0 = scene(n); L += [slow(t0 + 5, 90, 45.0, n), stat(n, 300, 27, 29, 90, 1)]
    # 4 p95 и пропуски вышли только из-за журнала -> НЕ ДОКАЗАНО
    n = 'io_everywhere'; t0 = scene(n); L += [slow(t0 + 1 + i * .2, 35, 3.0, n) for i in range(40)] + [stat(n, 200, 36, 37, 40, 40)]
    # 5 нарисовано ближе 0,3 м к глазу -> КРАСНЫЙ (кому: Камера)
    n = 'clip_car'; t0 = scene(n); L += [stat(n), f'CLIPG t={t0+3:.1f} seen_close=4 drawn_close=3 hidden=1']
    # 6 глаз внутри ящика куска (AABB) без подтверждения геометрией -> ЗЕЛЁНЫЙ* со справкой (не красный: ложная тревога TEST20b)
    n = 'eye_in_box'; t0 = scene(n); L += [stat(n), f'CAMCLIPSTAT t={t0+3:.1f} frames=30 eye_inside=2 near03=5 clip_pieces_max=2']
    n = 'eye_wall_vox'; t0 = scene(n); L += [stat(n), f'CAMCLIPSTAT t={t0+3:.1f} frames=30 eye_inside=30 near03=30 clip_pieces_max=2 wall_vox=4 wall_grid=30']
    n = 'eye_wall_front'; t0 = scene(n); L += [stat(n), f'CAMCLIPSTAT t={t0+3:.1f} frames=30 eye_inside=30 near03=30 clip_pieces_max=2 wall_vox=4 wall_grid=30 wall_front=3']
    n = 'eye_box_camin'; t0 = scene(n); L += [stat(n), f'CAMCLIPSTAT t={t0+3:.1f} frames=30 eye_inside=30 near03=30 clip_pieces_max=2', f'CAMIN t={t0+8:.1f} frames=300 any=2 eye=2 near=0 ground=0 car=0 person=0 occ=0']
    n = 'wall_nogrid'; t0 = scene(n); L += [stat(n), f'CAMCLIPSTAT t={t0+3:.1f} frames=30 eye_inside=0 near03=0 clip_pieces_max=0 wall_vox=0 wall_grid=0']
    # 7 CAMIN any > 0 -> КРАСНЫЙ
    n = 'camin_any'; t0 = scene(n); L += [stat(n), f'CAMIN t={t0+8:.1f} frames=300 any=3 eye=1 near=2 ground=0 car=1 person=0 occ=0']
    n = 'low_heap'; scene(n); L += [stat(n, heap=5.2)]
    # 8 видимые незагруженные клетки в середине сцены -> КРАСНЫЙ; в первую секунду после телепорта -> ЗЕЛЁНЫЙ*; телепорт у ириса -> КРАСНЫЙ
    n = 'undrawn'; t0 = scene(n); L += [row(t0 + 4, n, 20), stat(n, mv=20, mvmax=30)]
    n = 'undrawn_start'; t0 = scene(n); L += [row(t0 + 1.0, n, 20), stat(n, mv=20, mvmax=30)]
    n = 'undrawn_tp'; t0 = scene(n); L += [f'FOOT 1 2 3 0 t={t0+0.3:.1f}', row(t0 + 1.0, n, 20), stat(n, mv=20, mvmax=30)]
    n = 'undrawn_repair'; t0 = scene(n); L += [f'TELEPORT t={t0+4:.1f} kind=repair x=1 z=2', row(t0 + 4.8, n, 20), stat(n, mv=20, mvmax=30)]
    n = 'undrawn_iris'; t0 = scene(n); L += [f'FOOT 1 2 3 0 t={t0+5:.1f}', f'IRIS why=msn phase=open f=1.00 w=0.0 r=0 t={t0+5.4:.2f}', row(t0 + 6.0, n, 20), stat(n, mv=20, mvmax=30)]
    n = 'undrawn_late'; t0 = scene(n); L += [f'FOOT 1 2 3 0 t={t0+0.3:.1f}', row(t0 + 1.8, n, 20), stat(n, mv=20, mvmax=30)]   # строка на tp+1,5: окно 1,0 с не расширять -> КРАСНЫЙ (аудит 16.10)
    # склеенная строка: STAT приклеен к оборванной строке TQTOP -> сцена не должна пропасть
    n = 'glued_stat'; t0 = scene(n); L += ['TQTOP t=1.0 kt=0' + stat(n)]
    # 9 дальность на полу весь сценарий и кадр длинный -> КРАСНЫЙ
    n = 'dd_floor'; t0 = scene(n); L += [f'RFAST t={t0+i:.1f} sc={n} old=7 fps=28 work_ms=31 cpu_ms=31 ktris=30 draws=300 dd=150' for i in range(8)] + [stat(n, 300, 31.5, 33, 36, 3)]
    return L

EXPECT = {'undrawn_late': 'КРАСНЫЙ', 'glued_stat': 'ЗЕЛЁНЫЙ', 'ok_drive': 'ЗЕЛЁНЫЙ', 'slow_drive': 'КРАСНЫЙ', 'io_spike': 'ЗЕЛЁНЫЙ*', 'io_everywhere': 'НЕ ДОКАЗАНО', 'clip_car': 'КРАСНЫЙ',
          'eye_in_box': 'ЗЕЛЁНЫЙ*', 'eye_wall_vox': 'ЗЕЛЁНЫЙ*', 'eye_wall_front': 'КРАСНЫЙ', 'eye_box_camin': 'КРАСНЫЙ', 'camin_any': 'КРАСНЫЙ', 'undrawn': 'КРАСНЫЙ', 'undrawn_start': 'КРАСНЫЙ', 'undrawn_tp': 'ЗЕЛЁНЫЙ*', 'undrawn_repair': 'ЗЕЛЁНЫЙ*', 'undrawn_iris': 'КРАСНЫЙ', 'low_heap': 'КРАСНЫЙ', 'wall_nogrid': 'ЗЕЛЁНЫЙ*', 'dd_floor': 'КРАСНЫЙ'}

d = Path(tempfile.mkdtemp(prefix='hwv_')); (d / 'smoke.txt').write_text('\n'.join(build()) + '\n')
subprocess.run([sys.executable, '-I', str(ROOT / 'tools' / 'hw_verdict.py'), str(d), '--thr', str(ROOT / 'tests' / 'hw_thresholds.txt')], capture_output=True)
rows = {}
for ln in (d / 'ВЕРДИКТ.md').read_text().splitlines():
    c = [x.strip() for x in ln.split('|')]
    if len(c) > 6 and c[1] in EXPECT: rows[c[1]] = c[5]
bad = 0
for k, v in EXPECT.items():
    ok = rows.get(k) == v; bad += not ok
    print(('OK  ' if ok else 'FAIL'), k, 'ждали', v, 'получили', rows.get(k))
sys.exit(1 if bad else 0)

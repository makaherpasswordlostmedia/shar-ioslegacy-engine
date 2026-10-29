#!/usr/bin/env python3
"""BUILD_INFO.txt для набора выпуска/теста: ветка, коммит, влитые ветки (слияния первой линии), флаги по умолчанию (из исходников), sha EBOOT, чем собрано.
  tools/build_info.py EBOOT OUT_FILE [ИМЯ]"""
import sys, re, subprocess, hashlib, time
from pathlib import Path
root = Path(__file__).resolve().parents[1]
eboot, out = Path(sys.argv[1]), Path(sys.argv[2]); name = sys.argv[3] if len(sys.argv) > 3 else out.parent.name; extra = sys.argv[4] if len(sys.argv) > 4 else ''
g = lambda *a: subprocess.run(['git', '-C', str(root), *a], capture_output=True, text=True).stdout.strip()
FLAGS = [('viewer/main_state.h', ['DRAWDIST_MUL', 'DD_SIGMA_ON', 'DD_STEADY_OLD', 'TEST_OVERLAY_OFF']), ('viewer/car.h', ['CULL_SPHERE_OLD']), ('viewer/render_fast.h', ['CULL_SPHERE_OLD']),
         ('viewer/main_render.h', ['NEAR_CAR_DRAW_OLD', 'TQ_FAST_ON', 'NEON_GLOW_ON', 'NEON_GLOW_MAXTRI']), ('viewer/main_camera.h', ['CAM_GEOM_OLD']), ('viewer/police_fx.c', ['POLICE_FLASH_ON']),
         ('viewer/msn_view.c', ['NPC_GOV_OLD', 'NPC_GOV_DIST', 'ROAD_ARROW_OLD']), ('viewer/main_state.h', ['DEFER_FREE_OLD'])]
rows = []
for f, names in FLAGS:
    t = (root / f).read_text(errors='replace') if (root / f).exists() else ''
    for n in names:
        m = re.search(r'^#define ' + n + r'\s+(\S+)', t, re.M)
        if m and (n, m.group(1)) not in [(a, b) for a, b, _ in rows]: rows.append((n, m.group(1), f))
b = eboot.read_bytes(); sha = hashlib.sha256(b).hexdigest()
dirty = g('status', '--short', '--untracked-files=no')
lines = [f'BUILD_INFO · {name} · {time.strftime("%Y-%m-%d %H:%M")}', f'EBOOT: {eboot.name} {len(b)} Б sha256 {sha[:8]} (полный {sha})',
         f'ветка: {g("branch", "--show-current")}  коммит: {g("rev-parse", "--short", "HEAD")}  ({g("log", "-1", "--format=%s")[:100]})', ('флаги сборки: ' + extra) if extra else 'флаги сборки: по умолчанию', 'рабочая копия: ' + ('есть незакоммиченные изменения отслеживаемых файлов!' if dirty else 'чистая (коммит соответствует сборке)'),
         '', 'История финальной ветки от gemini/build a179cc73 (первая линия, новые сверху; коммит FINAL 3238c402 — одним коммитом всё влитое до 15.10 вечера, список в его сообщении: git show 3238c402):'] + ['  ' + l for l in g('log', 'a179cc73..HEAD', '--first-parent', '--format=%h %s').split('\n')[:40]] + \
        ['', 'Флаги по умолчанию в исходниках (значение — как стоит в #define; *_OLD=1 — прежнее поведение):'] + [f'  {n} = {v}   ({f})' for n, v, f in rows] + \
        ['', 'Время сборки вшито в EBOOT строкой «EBOOT <дата> <время>»; для сверки наборов — tools/verify_release.py (обнуляет её).']
out.write_text('\n'.join(lines) + '\n'); print(out)

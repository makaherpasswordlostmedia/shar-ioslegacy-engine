#!/usr/bin/env python3
"""№888 (Роб 23.10: «стрелки ◀ ▶ главного меню битые, пиксели поломаны в центре»): после пакета стрелки не должны терять рампу граней.
Собирает ui.shr с UI_SCRATCH, находит на страницах (page_*.png) картинки larrow/rarrow (17x18) и меряет среднюю ошибку цвета непрозрачных пикселей между
страницей (после CLUT8) и ровным ресемплом исходника — «поломка в центре» = тёмные штрихи, ошибка ~14 на общей странице ui1 и ~1-3 на своей странице.
  python3 tests/menu888/arrows_check.py [--old]   0 = PASS; --old (ARROWS_PAGE_OLD=1, красный контроль): 0 только если ошибка выше порога
Порог MAX_ERR = 6 (яркости 0..255). Нужен .venv (tools/ui_export.py), диск Роба — hit-and-run-web."""
import os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
MAX_ERR = 6.0
old = '--old' in sys.argv
sc = tempfile.mkdtemp(prefix='arrows888_')
env = dict(os.environ, UI_SCRATCH=sc, LEVEL='1', UI_PLACE_CODE='1', **({'ARROWS_PAGE_OLD': '1'} if old else {}))
py = ROOT / '.venv/bin/python'; py = str(py) if py.exists() else sys.executable
out = Path(sc) / 'ui.shr'
r = subprocess.run([py, str(ROOT / 'tools/ui_export.py'), '--out', str(out)], env=env, capture_output=True, text=True, cwd=ROOT)
if r.returncode: print(r.stdout[-400:], r.stderr[-800:]); sys.exit(2)
sys.path.insert(0, str(ROOT / 'tools')); os.environ['UI_SCRATCH'] = sc
import numpy as np
import ui_export as U
from PIL import Image
errs = {}
for name in ('larrow.png', 'rarrow.png'):
    bm = np.asarray(U.resample(U.Assets().images[name], 17, 18)).astype(int)
    mask = bm[..., 3] > 200; best = (1e9, None)
    for pg in sorted(Path(sc).glob('page_*.png')):
        P = np.asarray(Image.open(pg).convert('RGBA')).astype(int); H, W = P.shape[:2]
        for y in range(H - 17):
            for x in range(W - 16):
                sub = P[y:y + 18, x:x + 17]
                if (sub[..., 3] > 200).sum() < mask.sum() * .8: continue
                d = np.abs(sub[..., :3] - bm[..., :3])[mask].mean()
                if d < best[0]: best = (d, pg.name)
    errs[name] = best
    print(f'  {name}: ошибка {best[0]:.1f} на {best[1]} (порог {MAX_ERR})')
bad = [n for n, (d, _) in errs.items() if d > MAX_ERR]
ok = not bad
print(('PASS' if ok else 'FAIL ' + ','.join(bad)) + f' · tests/menu888/arrows_check.py{" --old" if old else ""}')
sys.exit((0 if not ok else 1) if old else (0 if ok else 1))

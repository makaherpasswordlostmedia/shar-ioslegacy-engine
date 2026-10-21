"""Правка Роба 329 (04.10: «над Барни нет обозначения, что он магазин — должен быть 3D-символ доллара»): Гомер у лавки Барни
(L1, 316 −131,74, лицом к продавцу) — над продавцом значок dollar из missgen (золотой «$»). Безголовый PPSSPP без звука.
КРАСНЫЙ: flag dollarold 1 — значка нет. python3 tests/npc/seller_dollar.py [EBOOT] -> 0 = PASS"""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]; SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def run(name, eboot, old):
    body = ['flag msn', 'wait 2'] + (['flag dollarold 1'] if old else []) + ['wait 26', 'foot 316 -131.74 1.5708', 'wait 2.5', 'shot b', 'end']
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write('\n'.join(body) + '\n'); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=500)
    p = ROOT / 'build/twins/scen/full' / name / 'b.png'
    if not p.exists(): return -1
    a = np.asarray(Image.open(p).convert('RGB'), int)[20:120, 200:300]   # область над продавцом (без радара и аватара)
    gold = (a[..., 0] > 180) & (a[..., 1] > 120) & (a[..., 1] < 210) & (a[..., 2] < 90)
    return int(gold.sum())

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red, green = run('dollar_red', eb, True), run('dollar_green', eb, False)
    print(f'золотых точек над продавцом: красный (dollarold) {red}, зелёный {green}')
    ok = red >= 0 and green - red >= 60   # фон кадра тоже бывает жёлтым (вывески): значок — прибавка золотых точек к красному кадру
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)

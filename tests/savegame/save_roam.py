"""Правка Роба 330 (04.10: «в нескольких случаях не могу сохранить — раздел меню серый»): на «воскресной прогулке» сюжетной миссии
(фаза 0, этап 5 m3 — «GET INTO YOUR VEHICLE») пауза свободной езды с активной строкой SAVE GAME. КРАСНЫЙ: flag saveroamold 1 —
прежнее (сохранение только на этапе 0 прогулки, строка серая). python3 tests/savegame/save_roam.py [EBOOT] -> 0 = PASS"""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]; SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def run(name, eboot, old):
    body = ['flag saves', 'flag msn', 'wait 2'] + (['flag saveroamold 1'] if old else []) + ['flag msnmainat -305', 'wait 4', 'press start', 'wait 1.5', 'shot p', 'end']
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write('\n'.join(body) + '\n'); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=500)
    p = ROOT / 'build/twins/scen/full' / name / 'p.png'
    if not p.exists(): return -1
    a = np.asarray(Image.open(p).convert('RGB'), int)[205:220, 160:320]   # строка SAVE GAME паузы
    return int(((a > 200).all(axis=2)).sum())

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red, green = run('save330_red', eb, True), run('save330_green', eb, False)
    print(f'белых точек в строке SAVE GAME: красный (saveroamold) {red}, зелёный {green}')
    ok = 0 <= red < 50 and green > 300
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)

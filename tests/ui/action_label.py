"""Правка Роба 206: прогон двух сцен (старт у Мардж; вышел из машины) с данным ui.shr; проверка: в журнале ACTTEXT «Talk To
Marge» и «Get Into Car», на снимке справа от значка △ (верх по центру) есть белые буквы подписи. python3 ... ИМЯ UI.SHR -> 0 = PASS"""
import os, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P
SCN = {'talk': 'wait 3\nflag msn\nwait 3\nshot hint\nend\n', 'car': 'scene start\nwait 3\npress triangle\nwait 3\nshot hint\nend\n'}

def run(name, ui, scn, timeout=150):
    out = C.OUT / 'action_label'; out.mkdir(parents=True, exist_ok=True)
    d, man = P.stage_full(out, name, scn, 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(ROOT / 'viewer/build/EBOOT.PBP', d / 'EBOOT.PBP')
    (d / 'ui.shr').unlink(); shutil.copy2(ui, d / 'ui.shr')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    for b in sorted(d.glob('*.bmp')): P.bmp_to_png(b, b.with_suffix('.png'))
    return d

def label_px(png):   # белые пиксели подписи у значка △ (верх): 255-яркие, в полосе y 10..75, x 150..440 (правка 272: под значком по центру)
    a = np.asarray(Image.open(png).convert('RGB'), int); w = a.shape[1]; k = w / 480
    box = a[int(10 * k):int(75 * k), int(150 * k):int(440 * k)]
    return int(((box.min(2) > 225)).sum())

if __name__ == '__main__':
    name, ui = sys.argv[1], sys.argv[2]; errs = []
    for key, want in (('talk', 'Talk To Marge'), ('car', 'Get Into Car')):
        d = run(f'{name}_{key}', ui, SCN[key]); s = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
        px = label_px(d / 'hint.png') if (d / 'hint.png').exists() else 0
        got = want in re.findall(r'ACTTEXT (.+)', s)
        print(f'{key}: ACTTEXT «{want}» {"есть" if got else "НЕТ"}, белых пикселей подписи {px}')
        if not got or px < 40: errs.append(key)
    print(f'{name}: {"OK" if not errs else "FAIL " + ",".join(errs)}'); sys.exit(1 if errs else 0)

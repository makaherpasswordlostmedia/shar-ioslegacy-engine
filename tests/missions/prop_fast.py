"""№prop-fast: прогон tests/missions/prop_fast.txt в безоконном PPSSPP на пакете RACE_PKG (по умолчанию build/test19_emu окна Сборка); печатает путь пакета. python3 ... EBOOT ИМЯ"""
import os, sys, subprocess, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P
eboot, tag = sys.argv[1], sys.argv[2]; SCEN = Path(os.environ['PF_SCEN']) if os.environ.get('PF_SCEN') else ROOT / 'tests/missions/prop_fast.txt'
PKG = Path(os.environ.get('RACE_PKG', str(Path.home() / 'Downloads/shar-psp-sonnet-16b-w/build/test19_emu')))
d = ROOT / 'build' / 'racepkg' / tag
if d.exists(): shutil.rmtree(d)
d.mkdir(parents=True)
for e in PKG.iterdir():
    if e.name in ('EBOOT.PBP', 'scenario.txt', 'smoke.txt', 'smokelog', 'blackbox.txt', 'blackbox_prev.txt') or e.name.startswith('shot'): continue
    os.symlink(e, d / e.name)
shutil.copy2(eboot, d / 'EBOOT.PBP'); (d / 'smokelog').write_text('')
(d / 'scenario.txt').write_text(SCEN.read_text())
home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
with (d / 'headless.log').open('w') as log:
    pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', '--timeout=600', str(d / 'EBOOT.PBP')], cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
    P.watch_no_window(pr, 660)
print(d)

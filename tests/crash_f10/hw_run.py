#!/usr/bin/env python3
"""Правка 252: сценарий в эмуляторе-проверяльщике «как железо» (tools/twins/ppsspp_hwcheck_build.sh -> build/twins/bin-hw).
   hw_run.py ИМЯ сценарий.txt      -> последняя строка: папка прогона; там smoke.txt и hwchk.txt (места, где PSP упала бы)
То же, что scen.py (skill shar-level-polish), только другой эмулятор: интерпретатор с проверками tools/twins/ppsspp_hwcheck.patch.
Переменные scen.py (SCEN_EBOOT, SCEN_OVERRIDE, SCEN_HOME, SCEN_ROOT, TWINS_ROOT) + HW_TRAP=1 — остановить игру на первом месте,
где PSP дала бы исключение (как железо); HW_TIMEOUT — предел прогона, с (по умолчанию 2400)."""
import os, sys, importlib.util, time
from pathlib import Path
ROOT = Path(os.environ.get('SCEN_ROOT') or Path(__file__).resolve().parents[2])
os.environ.setdefault('SCEN_ROOT', str(ROOT))
spec = importlib.util.spec_from_file_location('scen', os.path.expanduser('~/.claude/skills/shar-level-polish/scripts/scen.py'))
scen = importlib.util.module_from_spec(spec); spec.loader.exec_module(scen)
name, sc = sys.argv[1], sys.argv[2]
hw = scen.C.OUT / 'bin-hw' / 'PPSSPPHeadless'
if not hw.exists(): sys.exit(f'нет {hw}: tools/twins/ppsspp_hwcheck_build.sh')
scen.P.HEADLESS = hw
out = scen.C.OUT / 'scen' / 'full' / name
os.environ['SHAR_HWCHK'] = '1'; os.environ['SHAR_HWCHK_LOG'] = str(out / 'hwchk.txt')
if os.environ.get('HW_TRAP'): os.environ['SHAR_HWCHK_TRAP'] = '1'
t0 = time.time()
d = scen.run(name, open(sc).read().splitlines(), timeout=int(os.environ.get('HW_TIMEOUT', '2400')))
print('secs', round(time.time() - t0))
print(d)

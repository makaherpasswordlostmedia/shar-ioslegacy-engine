#!/usr/bin/env python3
"""Preserve native attempts, full data copies; only SMOKE_HEADLESS tools/smoke."""
import sys
from pathlib import Path
import unlock_emu as U
import emu_pickups_check as C
U.OUT=U.ROOT/'build/gates/bonus_pickups';U.OUT.mkdir(parents=True,exist_ok=True)
red='--red' in sys.argv;args=[a for a in sys.argv[1:] if a!='--red']
d,bad=U.run('old' if red else 'green',Path(args[0]).resolve(),(U.HERE/'emu_pickups.txt').read_text(),timeout=600)
print('native:',d,'runner:',bad or 'END/errors0')
sys.argv=[str(U.HERE/'emu_pickups_check.py'),str(d)]+(['--expect-fail'] if red else [])
rc=C.main()
if bad:print('FAIL native runner:',bad)
sys.exit(rc or int(bool(bad)))

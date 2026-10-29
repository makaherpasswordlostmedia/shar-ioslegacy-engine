#!/usr/bin/env python3
"""Keep every native screens attempt; only the authorized headless smoke runner."""
import os, sys
from pathlib import Path
import unlock_emu as U
import screens_check as C
U.OUT = U.ROOT / 'build/gates/bonus_screens'
U.OUT.mkdir(parents=True, exist_ok=True)
red = '--red' in sys.argv
args = [a for a in sys.argv[1:] if a != '--red']
d, bad = U.run('red' if red else 'green', Path(args[0]).resolve(), (U.HERE/'screens_scenario.txt').read_text(), timeout=600)
print('native:', d, 'runner:', bad or 'END/errors=0')
sys.argv = [str(U.HERE/'screens_check.py'), str(d)] + (['--expect-fail'] if red else [])
rc = C.main()
if bad: print('FAIL native runner:', bad)
sys.exit(rc or int(bool(bad)))

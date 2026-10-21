#!/usr/bin/env python3
"""Reject the real pre-probe menu run (zero measured menu frames), not synthetic timing."""
import argparse,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('kwik');p.add_argument('before_menu');p.add_argument('options');a=p.parse_args()
cmd=[sys.executable,str(Path(__file__).with_name('gate.py')),a.kwik,a.before_menu,a.options,'--kwik-before',a.kwik,'--menu-before',a.before_menu]
r=subprocess.run(cmd,capture_output=True,text=True);print(r.stdout+r.stderr)
assert r.returncode==1 and 'missing menu measurement / too few frames' in r.stdout
print('PASS real pre-probe menu rejected; no timing copied from gameplay STAT')

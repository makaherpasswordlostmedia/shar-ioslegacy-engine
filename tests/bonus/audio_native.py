#!/usr/bin/env python3
"""Headless namespace round-trip, actual stream requests, no PSP performance claim"""
import re,sys
from pathlib import Path
p=Path(sys.argv[1]);s=(p/'smoke.txt').read_text();fx=(p/'sfxlog.txt').read_text()
assert len(re.findall(r'^SFX countdown_beeps ',fx,re.M))==3
assert 'BONUS ev=start ' in s and 'BONUS ev=done ' in s and 'BONUS ev=exit ok=1' in s and s.rstrip().endswith('END')
race=s.index('STREAM s=music track=casio_tune01 ')
result=s.index('STREAM s=music track=lose_mini_game02 ')
exit=s.index('BONUS ev=exit ok=1')
frontend=s.index('STREAM s=music track=simpsons_theme ',exit)
assert race<result<exit<frontend
assert re.search(r'^SFX (small|med|lrg)_crash ',fx,re.M)
for name in ['readerr','allocfail','geskip','memfail','gebad']:assert not re.search(r'\b'+name+r' [1-9]',s)
print('PASS native 3 beeps/race/result/city bank restore/END/errors0; FPS is emulator only')

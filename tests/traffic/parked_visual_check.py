#!/usr/bin/env python3
"""Require actual hijack, own-car selection, return and seat transition."""
import re,sys
from pathlib import Path
s=Path(sys.argv[1]).read_text(errors='replace')
patterns=[r'CARJACK model=schoolbu',r'TRIJACK ji=-2',r'CARJACK back',r'IRIS why=seat phase=done',r'SHOT own_back [\d.]+ pos 300\.00 [\d.]+ 180\.00',r'(?m)^END$']
last=0
for p in patterns:
 m=re.search(p,s[last:])
 if not m:print('FAIL missing or out of order: '+p);raise SystemExit(1)
 last+=m.end()
print('PASS parked car: hijack, return selection, seat and original position; END')

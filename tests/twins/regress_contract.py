#!/usr/bin/env python3
"""The comparison must fail when its observations or identity are absent/bad."""
import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'tools/twins/regress.py'
s=importlib.util.spec_from_file_location('regress',P);R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
ref={'p95 мс':'7.25'};good=dict(p95=8.25,missed=0,memfail=0,allocfail=0,readerr=0,gebad=0,geskip=0,missvis=0,timeout=False)
assert not R.compare(ref,True,good)
for key,val in [('p95',8.26),('missed',1),('memfail',1),('allocfail',1),('readerr',1),('gebad',1),('geskip',1),('missvis',1),('timeout',True)]:
 bad={**good,key:val};assert R.compare(ref,True,bad),key
assert R.compare(ref,False,good) and R.compare(ref,True,None)
assert R.compare(ref,True,{'p95':7}), 'missing counters escaped'
print('PASS p95 boundary; red9 counters/timing + missing END/STAT/counters caught')

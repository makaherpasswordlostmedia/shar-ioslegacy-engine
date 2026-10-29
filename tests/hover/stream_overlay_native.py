#!/usr/bin/env python3
"""Same native contract on green and CAR_STREAM_OLD; missing fixtures aren't red."""
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import smoke_report as S
p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
f=a.run/'smoke.txt'
if not f.exists():raise SystemExit('ERROR missing native run')
text=f.read_text();ended,_,stats,_=S.parse(a.run)
assert ended and 'LEVEL ev=load n=7 loaded=7' in text and re.search(r'CARSND car=ship profile=[1-9]',text),'invalid L7/ship/END fixture'
events=re.findall(r'^STREAM s=car track=(\S+).*t=([\d.]+)',text,re.M)
start=[float(t) for tr,t in events if tr=='ov_ship_overlay'];stop=[float(t) for tr,t in events if tr=='-' and start and float(t)>start[0]]
ok=len(start)==1 and bool(stop)
for k in ('missed','allocfail','memfail','readerr','geskip','gebad','missvis'):assert stats['ship'].get(k)==0,k
print(('PASS' if ok else 'FAIL')+' '+json.dumps(dict(start=start,stop=stop,END=ended,ship=stats['ship'])))
raise SystemExit(0 if ok else 1)

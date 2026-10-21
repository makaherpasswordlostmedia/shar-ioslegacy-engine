#!/usr/bin/env python3
"""Real native result deadline from first winner, independent of human finish."""
import argparse,json,re,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--expect-old',action='store_true');a=p.parse_args()
text=(a.run/'smoke.txt').read_text();errors=[];result=[];cur=None;fin=[];done=False
if 'END' not in text.split():errors.append('missing native END')
def close_open():
 if cur is not None and fin and not done:errors.append('track '+cur+': race ended without result after opponent finish')
for line in text.splitlines():
 if not line.startswith('BONUS '):continue
 v=dict(re.findall(r'(\w+)=(\S+)',line));kind=v.get('ev')
 if kind=='start':close_open();cur=v.get('track');fin=[];done=False
 elif kind=='finish':fin.append(v)
 elif kind=='done':
  done=True
  if not fin:errors.append('result without finish');continue
  first=min(float(f['total']) for f in fin);end=float(v['time']);delay=end-first
  result.append(dict(track=cur,first_finish=first,result=end,delay=delay,dnf=v['dnf']))
  if delay>20.05:errors.append('track '+cur+': delay>20.05s from first winner')
  if any(x=='1' for x in v['dnf'].split(',')) and not 19.95<=delay<=20.05:errors.append('track '+cur+': DNF timeout outside one-frame+printed precision')
close_open()
if {r['track'] for r in result}!={'4','7'} and not a.expect_old:errors.append('missing both complete native races b04/b07')
print(json.dumps(dict(status='FAIL' if errors else 'PASS',results=result,errors=errors),indent=2))
if a.expect_old:
 caught=any('delay>20.05' in e or 'without result' in e for e in errors) and 'missing native END' not in errors
 print('PASS actual native OLD first-winner violation caught' if caught else 'FAIL old not caught');sys.exit(not caught)
sys.exit(bool(errors))

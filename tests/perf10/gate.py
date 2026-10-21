#!/usr/bin/env python3
"""Reject all raw explosion-frame spikes, including trace I/O hidden by STAT subtraction."""
import argparse,json,sys
from pathlib import Path

def check(run):
 log=(run/'smoke.txt').read_text(errors='replace');errors=[];result={}
 if 'END' not in log.split():errors.append('incomplete run')
 if 'CARBOOM ' not in log:errors.append('no actual explosion')
 for scene in ['M313_drive','M313_smoke_fire','M313_boom']:
  rows=[s.split() for s in log.splitlines() if s.startswith('STAT '+scene+' ')]
  if len(rows)!=1:errors.append(scene+': missing STAT');continue
  row=dict(zip(rows[0][2::2],rows[0][3::2]));result[scene]=row
  if int(row['frames'])<300:errors.append(scene+': insufficient interval')
  if float(row['max'])>33.4:errors.append(scene+': work max >33.4ms')
  for key in ['missed','missvis','readerr','allocfail','geskip','memfail','gebad']:
   if int(row[key]):errors.append(scene+': '+key)
  # Goto is an explicit loading command in drive/smoke; boom has none.
  # For boom keep EVERY sample, including settling and photos, without I/O subtraction.
  samples=[]
  for line in log.splitlines():
   r=line.split()
   if len(r)<8 or r[1]!=scene:continue
   try:float(r[0]);value=float(r[4])
   except ValueError:continue
   if scene=='M313_boom' or 'settling' not in r:samples.append(value)
  if len(samples)<8:errors.append(scene+': insufficient raw samples')
  peak=max(samples,default=0);result[scene]['raw_workmax_ms']=peak
  if peak>33.4:errors.append(scene+': raw max >33.4ms (trace included)')
 result.update(status='FAIL' if errors else 'PASS',errors=errors,budget_max_ms=33.4)
 return errors,result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();errors,result=check(a.run)
 (a.run/'perf10-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(bool(errors))

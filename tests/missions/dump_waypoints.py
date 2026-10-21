#!/usr/bin/env python3
"""Run real mission cargo bindings; old next-waypoint comparison must fail."""
import argparse,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',type=Path,default=ROOT/'build/ship_stage');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 levels=[a.stage/'level01.msn']+[a.stage/f'l{i}/level0{i}.msn' for i in range(2,8)]
 source=ROOT/'viewer/mission/msn_run.c';old=a.out/'msn_old.c';code=source.read_text();assert code.count('e.waypoint >= rt->bind_wp[b]')==1;old.write_text(code.replace('e.waypoint >= rt->bind_wp[b]','e.waypoint > rt->bind_wp[b]'))
 for name,runtime,expected in [('green',source,0),('red',old,1)]:
  binary=a.out/name
  subprocess.run(['cc','-std=c11','-O2','-I',str(ROOT/'viewer'),'-I',str(ROOT/'viewer/mission'),str(ROOT/'tests/missions/dump_waypoints.c'),str(runtime),str(ROOT/'viewer/mission/msn_ops.c'),str(ROOT/'viewer/mission/msn_file.c'),'-lm','-o',str(binary)],check=True)
  r=subprocess.run([str(binary),*map(str,levels)],capture_output=True,text=True);(a.out/(name+'.log')).write_text(r.stdout+r.stderr);print((r.stdout.splitlines() or [f'{name}: no result, rc={r.returncode}'])[-1]);assert r.returncode==expected,(name,r.returncode)
 print('PASS authored cargo bindings; old one-waypoint delay detected')
if __name__=='__main__':main()
